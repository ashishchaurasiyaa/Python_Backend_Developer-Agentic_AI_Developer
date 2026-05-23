# Design Dropbox (Cloud File Storage & Sync)

---

## 1. Requirements

### Functional
- Upload / download files (any size, up to 5 GB per file)
- File sync across devices (auto-detect changes, push updates)
- Folder sharing & collaboration (read/write permissions)
- File versioning (restore previous versions, 30-day history)
- Conflict resolution (two devices edit same file offline)
- Search files by name / content
- Selective sync (choose which folders to sync per device)

### Non-Functional
- 500M users, 100M DAU
- 50B files stored total (~5 TB metadata)
- 1 PB new data added/day at peak
- File upload < 5 min for 1 GB on good connection
- Sync latency < 5s (time from save to visible on another device)
- 99.99% durability (no file loss), 99.9% availability

---

## 2. Scale Estimation

| Metric | Calculation | Result |
|--------|-------------|--------|
| Storage | 500M users × 10 GB avg | ~5 PB total |
| Upload QPS | 100M DAU × 5 uploads/day ÷ 86400 | ~5,800 QPS |
| Download QPS | 100M DAU × 20 downloads/day ÷ 86400 | ~23K QPS |
| Metadata size | 50B files × 100B metadata/file | ~5 TB |
| Delta sync saves | 100M DAU × 10 saves/day × 10% changed blocks | ~11.6M block uploads/sec |

---

## 3. Architecture

```
Desktop/Mobile Client
  │  (local watcher: inotify/FSEvents/ReadDirectoryChanges)
  │
  ▼
API Gateway (auth + routing)
  │
  ├── Upload Service → Block Storage (S3/GCS)
  ├── Metadata Service → PostgreSQL (sharded) + Elasticsearch
  ├── Sync Service (WebSocket / long-poll) → Redis Pub/Sub
  ├── Version Service → DynamoDB
  ├── Notification Service → Kafka → WebSocket push
  └── Search Service → Elasticsearch

                   ┌──────────────────┐
                   │      Kafka        │
                   │  file_uploaded    │
                   │  sync_event       │
                   │  share_changed    │
                   └──────────────────┘
```

---

## 4. Chunked Upload with Delta Sync

```python
"""
Key Insight: Don't transfer the whole file — only changed CHUNKS.

File → split into 4 MB blocks → hash each block (SHA-256)
Client sends: [list of (chunk_id, sha256)] for changed file
Server replies: which chunk_ids it already has (dedup)
Client uploads only: MISSING chunks

This is called "rsync algorithm" / content-defined chunking.
"""

import hashlib
from dataclasses import dataclass, field

CHUNK_SIZE = 4 * 1024 * 1024   # 4 MB


@dataclass
class FileChunk:
    chunk_id: str       # SHA-256 of chunk content (content-addressable)
    offset: int         # byte offset in file
    size: int
    data: bytes = field(default=b"", repr=False)


class ChunkManager:
    """Client-side: split file into chunks, compute hashes."""

    @staticmethod
    def split_file(file_path: str) -> list[FileChunk]:
        chunks = []
        offset = 0
        with open(file_path, "rb") as f:
            while True:
                data = f.read(CHUNK_SIZE)
                if not data:
                    break
                chunk_id = hashlib.sha256(data).hexdigest()
                chunks.append(FileChunk(chunk_id=chunk_id, offset=offset,
                                        size=len(data), data=data))
                offset += len(data)
        return chunks

    @staticmethod
    def compute_file_hash(chunks: list[FileChunk]) -> str:
        """Deterministic file hash = hash of all chunk hashes concatenated."""
        h = hashlib.sha256()
        for chunk in chunks:
            h.update(chunk.chunk_id.encode())
        return h.hexdigest()


class UploadService:
    """
    Server-side: handle chunked upload.
    Implements content-addressable storage (CAS):
    Same chunk content → stored once, referenced by many files.
    """

    async def initiate_upload(self, user_id: str, file_path: str,
                               file_hash: str, chunks: list[dict]) -> dict:
        """
        Client sends file metadata + list of (chunk_id, size) pairs.
        Server responds with which chunks need to be uploaded.
        """
        existing = await self._check_existing_chunks([c["chunk_id"] for c in chunks])
        missing_chunks = [c for c in chunks if c["chunk_id"] not in existing]

        # Create upload session
        session_id = await self.db.create_upload_session({
            "user_id":    user_id,
            "file_path":  file_path,
            "file_hash":  file_hash,
            "chunks":     chunks,
            "status":     "in_progress"
        })

        return {
            "session_id":     session_id,
            "missing_chunks": [c["chunk_id"] for c in missing_chunks],
            "upload_urls":    await self._generate_presigned_urls(missing_chunks)
        }

    async def upload_chunk(self, session_id: str,
                            chunk_id: str, data: bytes) -> bool:
        """
        Client uploads individual chunk directly to S3 (presigned URL).
        After upload, client notifies server.
        """
        # Verify content hash matches chunk_id
        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash != chunk_id:
            raise ValueError(f"Chunk hash mismatch: expected {chunk_id}, got {actual_hash}")

        # Store chunk in S3 (content-addressable path)
        await self.s3.put_object(
            Bucket="dropbox-chunks",
            Key=f"chunks/{chunk_id}",
            Body=data,
            ChecksumSHA256=chunk_id
        )

        # Mark chunk as received in session
        await self.db.mark_chunk_received(session_id, chunk_id)
        return True

    async def finalize_upload(self, session_id: str) -> dict:
        """
        All chunks uploaded. Create file record in metadata DB.
        Triggers sync notification to other devices.
        """
        session = await self.db.get_upload_session(session_id)

        # Create file version record
        version_id = await self.version_service.create_version({
            "user_id":   session["user_id"],
            "file_path": session["file_path"],
            "file_hash": session["file_hash"],
            "chunks":    session["chunks"],
            "size":      sum(c["size"] for c in session["chunks"])
        })

        # Update file metadata
        file_record = await self.metadata_service.upsert_file({
            "user_id":    session["user_id"],
            "path":       session["file_path"],
            "version_id": version_id,
            "file_hash":  session["file_hash"],
            "size":       sum(c["size"] for c in session["chunks"]),
            "modified_at": __import__("time").time()
        })

        # Notify other devices via Kafka
        await self.kafka.send("file_events", {
            "event":     "file_uploaded",
            "user_id":   session["user_id"],
            "file_path": session["file_path"],
            "version_id": version_id
        })

        await self.db.update_upload_session(session_id, "completed")
        return {"file_id": file_record["file_id"], "version_id": version_id}

    async def _check_existing_chunks(self, chunk_ids: list[str]) -> set[str]:
        """Check S3/DB which chunks already exist (deduplication)."""
        # Batch check
        existing = set()
        for chunk_id in chunk_ids:
            exists = await self.redis.exists(f"chunk_exists:{chunk_id}")
            if exists:
                existing.add(chunk_id)
            else:
                # Check S3
                try:
                    await self.s3.head_object(Bucket="dropbox-chunks", Key=f"chunks/{chunk_id}")
                    existing.add(chunk_id)
                    await self.redis.setex(f"chunk_exists:{chunk_id}", 86400, "1")
                except Exception:
                    pass
        return existing

    async def _generate_presigned_urls(self, chunks: list[dict]) -> dict:
        """Generate S3 presigned URLs for direct browser/client upload."""
        urls = {}
        for chunk in chunks:
            url = await self.s3.generate_presigned_url(
                "put_object",
                Params={"Bucket": "dropbox-chunks", "Key": f"chunks/{chunk['chunk_id']}"},
                ExpiresIn=3600
            )
            urls[chunk["chunk_id"]] = url
        return urls
```

---

## 5. File Metadata Service

```python
"""
Metadata schema (PostgreSQL, sharded by user_id):

files table:
  file_id     UUID (PK)
  user_id     UUID (FK, shard key)
  path        TEXT           -- /Documents/report.pdf
  name        TEXT
  size        BIGINT
  file_hash   TEXT           -- SHA-256 of file
  version_id  UUID (FK)
  is_deleted  BOOLEAN
  created_at  TIMESTAMPTZ
  modified_at TIMESTAMPTZ

file_chunks table:
  file_version_id  UUID
  chunk_id         TEXT       -- SHA-256 of chunk
  offset           BIGINT
  size             INTEGER
  order_idx        INTEGER
"""

class MetadataService:

    async def get_file(self, user_id: str, path: str) -> dict | None:
        """Get file metadata including chunk list for download."""
        cache_key = f"file_meta:{user_id}:{path}"
        cached = await self.redis.get(cache_key)
        if cached:
            import json
            return json.loads(cached)

        file_row = await self.db.query_one(
            "SELECT * FROM files WHERE user_id=$1 AND path=$2 AND is_deleted=FALSE",
            user_id, path
        )
        if not file_row:
            return None

        # Get chunks for current version
        chunks = await self.db.query_many(
            "SELECT chunk_id, offset, size FROM file_chunks "
            "WHERE file_version_id=$1 ORDER BY order_idx",
            file_row["version_id"]
        )

        result = {**file_row, "chunks": list(chunks)}
        import json
        await self.redis.setex(cache_key, 300, json.dumps(result, default=str))
        return result

    async def list_folder(self, user_id: str, folder_path: str) -> list[dict]:
        """List all files/folders under given path."""
        return await self.db.query_many(
            """SELECT file_id, path, name, size, modified_at,
                      (path LIKE $3 || '/%/%') as is_nested
               FROM files
               WHERE user_id=$1 AND path LIKE $2
               AND is_deleted=FALSE
               ORDER BY path""",
            user_id,
            f"{folder_path}/%",
            folder_path
        )

    async def move_file(self, user_id: str,
                         src_path: str, dst_path: str) -> bool:
        """Move/rename file. Updates path in DB, no data moved in S3."""
        await self.db.execute(
            "UPDATE files SET path=$3, name=$4, modified_at=NOW() "
            "WHERE user_id=$1 AND path=$2",
            user_id, src_path, dst_path, dst_path.split("/")[-1]
        )
        await self.redis.delete(f"file_meta:{user_id}:{src_path}")
        await self.redis.delete(f"file_meta:{user_id}:{dst_path}")

        await self.kafka.send("file_events", {
            "event": "file_moved", "user_id": user_id,
            "src": src_path, "dst": dst_path
        })
        return True

    async def delete_file(self, user_id: str, path: str) -> bool:
        """Soft delete — file retained for 30 days for recovery."""
        await self.db.execute(
            "UPDATE files SET is_deleted=TRUE, deleted_at=NOW() "
            "WHERE user_id=$1 AND path=$2",
            user_id, path
        )
        await self.redis.delete(f"file_meta:{user_id}:{path}")
        await self.kafka.send("file_events", {
            "event": "file_deleted", "user_id": user_id, "path": path
        })
        return True
```

---

## 6. Sync Engine

```python
"""
Sync Protocol:
1. Client watches local filesystem (inotify on Linux, FSEvents on macOS)
2. Change detected → compute new chunk hashes
3. Diff against last known server state
4. Upload only changed chunks
5. Server sends sync events to other devices via WebSocket

Long-poll fallback for clients that can't maintain WebSocket.
"""

import asyncio
import json
from collections import defaultdict

class SyncService:
    """
    Server-side sync coordinator.
    Maintains per-user WebSocket connections across all their devices.
    """

    def __init__(self):
        # user_id → set of (device_id, websocket)
        self.connections: dict[str, dict[str, object]] = defaultdict(dict)

    async def connect(self, user_id: str, device_id: str, websocket):
        """Device connects and subscribes to sync events."""
        self.connections[user_id][device_id] = websocket
        # Send delta since device's last sync
        await self._send_pending_changes(user_id, device_id, websocket)

    async def disconnect(self, user_id: str, device_id: str):
        self.connections[user_id].pop(device_id, None)

    async def notify_file_change(self, user_id: str, event: dict,
                                  exclude_device: str | None = None):
        """Push file change event to all of user's devices."""
        message = json.dumps(event)
        dead_devices = []

        for device_id, ws in self.connections[user_id].items():
            if device_id == exclude_device:
                continue
            try:
                await ws.send_text(message)
            except Exception:
                dead_devices.append(device_id)

        for d in dead_devices:
            self.connections[user_id].pop(d, None)

    async def get_delta(self, user_id: str, device_id: str,
                         since_cursor: str) -> dict:
        """
        Return all file changes since device's last sync cursor.
        Cursor = timestamp or event_id.
        """
        events = await self.db.query_many(
            "SELECT * FROM sync_events WHERE user_id=$1 AND event_id > $2 "
            "ORDER BY event_id LIMIT 1000",
            user_id, since_cursor
        )
        new_cursor = events[-1]["event_id"] if events else since_cursor

        return {
            "events":    list(events),
            "cursor":    new_cursor,
            "has_more":  len(events) == 1000
        }

    async def _send_pending_changes(self, user_id: str,
                                     device_id: str, websocket):
        """Send all changes that happened while device was offline."""
        last_cursor = await self.db.get_device_cursor(user_id, device_id)
        delta = await self.get_delta(user_id, device_id, last_cursor)
        if delta["events"]:
            await websocket.send_text(json.dumps({
                "type": "delta",
                "data": delta
            }))
```

---

## 7. Conflict Resolution

```python
"""
Conflict scenario:
- Device A edits report.docx while offline
- Device B also edits report.docx while offline
- Both come online → CONFLICT

Strategy: "Last Writer Wins" for simple cases.
For true conflict: create conflict copy "report (Bob's conflicted copy).docx"
This is what Dropbox actually does.
"""

class ConflictResolver:

    async def resolve_upload(self, user_id: str, file_path: str,
                              new_hash: str, device_id: str,
                              client_modified_at: float) -> dict:
        """
        Called when client uploads a file.
        Detect conflict if server version was modified after client's
        last known state.
        """
        current = await self.metadata_service.get_file(user_id, file_path)

        if not current:
            # New file — no conflict
            return {"action": "upload", "path": file_path}

        if current["file_hash"] == new_hash:
            # Content identical — no-op
            return {"action": "noop"}

        # Check if client's version is based on server's current version
        server_modified_at = current["modified_at"]
        device_cursor = await self.db.get_device_last_sync(user_id, device_id)

        if server_modified_at > device_cursor:
            # Server was modified after device last synced → CONFLICT
            conflict_path = self._make_conflict_path(
                file_path, device_id, client_modified_at
            )
            return {
                "action":        "conflict",
                "original_path": file_path,
                "conflict_path": conflict_path,
                "message":       f"File was modified on another device. "
                                 f"Your version saved as: {conflict_path}"
            }

        # No conflict — device's version is newer
        return {"action": "upload", "path": file_path}

    def _make_conflict_path(self, path: str, device_id: str,
                             ts: float) -> str:
        """Generate conflict copy filename."""
        from datetime import datetime
        import os
        stem, ext = os.path.splitext(path)
        date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        return f"{stem} (conflicted copy {device_id[:8]} {date_str}){ext}"
```

---

## 8. File Versioning

```python
"""
Each file upload creates a new version.
Versions retained 30 days (free) / unlimited (paid).
Download by version: fetch specific version's chunks from S3.
Deduplication: chunks shared across versions stored only once.
"""

class VersionService:

    async def create_version(self, data: dict) -> str:
        """Create new file version record."""
        import uuid, time
        version_id = str(uuid.uuid4())
        await self.db.execute(
            "INSERT INTO file_versions(version_id,user_id,file_path,"
            "file_hash,chunks,size,created_at) VALUES($1,$2,$3,$4,$5,$6,$7)",
            version_id, data["user_id"], data["file_path"],
            data["file_hash"], __import__("json").dumps(data["chunks"]),
            data["size"], time.time()
        )
        return version_id

    async def list_versions(self, user_id: str, file_path: str,
                             limit: int = 30) -> list[dict]:
        return await self.db.query_many(
            "SELECT version_id, file_hash, size, created_at FROM file_versions "
            "WHERE user_id=$1 AND file_path=$2 "
            "ORDER BY created_at DESC LIMIT $3",
            user_id, file_path, limit
        )

    async def restore_version(self, user_id: str, file_path: str,
                               version_id: str) -> dict:
        """Restore file to a previous version."""
        version = await self.db.query_one(
            "SELECT * FROM file_versions WHERE version_id=$1 AND user_id=$2",
            version_id, user_id
        )
        if not version:
            raise ValueError("Version not found")

        # Create NEW version pointing to old version's chunks (no data copy!)
        new_version_id = await self.create_version({
            "user_id":   user_id,
            "file_path": file_path,
            "file_hash": version["file_hash"],
            "chunks":    __import__("json").loads(version["chunks"]),
            "size":      version["size"]
        })

        # Update current file pointer
        await self.metadata_service.update_file_version(
            user_id, file_path, new_version_id, version["file_hash"]
        )

        await self.kafka.send("file_events", {
            "event":      "file_restored",
            "user_id":    user_id,
            "file_path":  file_path,
            "version_id": new_version_id
        })
        return {"version_id": new_version_id, "restored_from": version_id}

    async def cleanup_old_versions(self, retention_days: int = 30):
        """Cron job: delete versions older than retention period."""
        cutoff = __import__("time").time() - retention_days * 86400
        old_versions = await self.db.query_many(
            "SELECT version_id, chunks FROM file_versions WHERE created_at < $1",
            cutoff
        )
        for version in old_versions:
            # Check if chunks are still referenced by newer versions
            chunks = __import__("json").loads(version["chunks"])
            for chunk in chunks:
                ref_count = await self.db.query_one(
                    "SELECT COUNT(*) as cnt FROM file_chunks WHERE chunk_id=$1",
                    chunk["chunk_id"]
                )
                if ref_count["cnt"] == 1:
                    # Only referenced by this version → safe to delete from S3
                    await self.s3.delete_object(
                        Bucket="dropbox-chunks",
                        Key=f"chunks/{chunk['chunk_id']}"
                    )

            await self.db.execute(
                "DELETE FROM file_versions WHERE version_id=$1",
                version["version_id"]
            )
```

---

## 9. Failure Scenarios

| Scenario | Solution |
|----------|----------|
| Upload interrupted mid-way | Resume upload: client re-sends chunk list, server tells which chunks missing |
| Client crashes during sync | Re-run sync on reconnect using cursor (event_id). Idempotent operations |
| S3 chunk durability | S3 11-nines durability + cross-region replication for critical data |
| Metadata DB overload | Shard by user_id. Read replicas for list operations |
| Conflict data loss | Never overwrite — create conflict copy. User can manually merge |
| Disk full on client | Selective sync + smart caching (evict least-recently-accessed local files) |

---

## 10. Interview Questions

**Q1: How does Dropbox reduce upload bandwidth?**
> Content-defined chunking + deduplication. File split into 4 MB blocks, each identified by SHA-256 hash. Before uploading, client tells server all chunk hashes. Server responds with which chunks it already has (from other files/versions). Client uploads only missing chunks. If a 100 MB file has 90 MB unchanged, only 10 MB is transferred. Cross-user deduplication: if two users have identical files, chunks stored once.

**Q2: How does sync work when a device is offline?**
> Server maintains a sync cursor (event_id) per device. When device reconnects, it sends its last cursor. Server returns all events since that cursor (file creates/updates/deletes/moves). Device applies these changes. For conflicts (device and server both modified), create a "conflicted copy" rather than losing either version.

**Q3: How does Dropbox handle large file uploads?**
> Multipart / chunked upload. File split into 4 MB blocks, each uploaded independently (can be parallel). S3 multipart upload for each chunk (up to 10,000 parts per upload). If chunk fails, retry just that chunk. Only on finalize (all chunks received) does the file version become visible. Presigned S3 URLs allow direct client → S3 upload bypassing server bandwidth.

**Q4: How is file versioning implemented without huge storage costs?**
> Content-addressable storage (CAS): chunks stored by their SHA-256 hash. Multiple versions share chunks — if version 2 changes only 1 block of a 100-block file, 99 blocks are shared with version 1 (same S3 objects). Version records in DB store only chunk lists (SHA-256 references), not data. Storage grows only with actual changes.

**Q5: How to implement folder sharing?**
> "Namespace" abstraction: a shared folder is a namespace with an owner. Members get an entry in `folder_members(namespace_id, user_id, permission)`. Each member's file tree has a mount point pointing to the namespace. Changes to shared folder → events fanned out to all members. Permissions checked on every operation via the namespace_id.

**Q6: How to handle the metadata DB at 5 TB scale?**
> Shard PostgreSQL by user_id (consistent hash). Each shard holds ~1/N of users' files. Queries within a user's files always go to one shard (all files have same user_id). Cross-user queries (search all shares) use Elasticsearch. Read replicas for list/search operations. Caching: Redis for frequently accessed file metadata (5-min TTL).
