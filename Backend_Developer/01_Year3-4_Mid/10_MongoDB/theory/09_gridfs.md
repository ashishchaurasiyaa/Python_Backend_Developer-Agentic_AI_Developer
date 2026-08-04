# MongoDB GridFS

## Why It Matters

MongoDB documents have a hard **16MB size limit** — GridFS is the built-in
mechanism for storing files larger than that (videos, large PDFs, ML model
artifacts) by chunking them across multiple documents. Low-frequency topic in
practice — most teams reach for S3/object storage even in MongoDB-primary
systems — but it's a fair "do you know MongoDB's file-storage answer"
question if a JD mentions MongoDB-native file handling.

Senior interview: "Why would you use GridFS instead of just storing files in
S3 and a URL reference in MongoDB?" → almost always S3 wins; know GridFS
exists and its narrow legitimate use case (below).

---

## Core Concept — how GridFS actually stores a file

```
GridFS splits a file into 255KB chunks (default), stored across TWO collections:

fs.files   → ONE document per file: filename, length, uploadDate, metadata
fs.chunks  → MANY documents per file: files_id (ref), n (chunk order), data (binary)

Uploading a 10MB video:
fs.files:  { _id: ObjectId("..."), filename: "video.mp4", length: 10485760, ... }
fs.chunks: { files_id: ObjectId("..."), n: 0, data: <255KB binary> }
           { files_id: ObjectId("..."), n: 1, data: <255KB binary> }
           ... (40 chunks total for a 10MB file)
```

This chunking is exactly why GridFS bypasses the 16MB document limit — no
single document ever holds more than one chunk.

---

## PyMongo GridFS usage

```python
from pymongo import MongoClient
import gridfs

client = MongoClient("mongodb://localhost:27017")
db = client["myapp"]
fs = gridfs.GridFS(db)

# Upload a file
with open("report.pdf", "rb") as f:
    file_id = fs.put(f, filename="report.pdf", content_type="application/pdf",
                      metadata={"uploaded_by": "user_123"})

# Download a file
grid_out = fs.get(file_id)
data = grid_out.read()

# Stream download (don't load whole file into memory at once)
with open("downloaded_report.pdf", "wb") as out:
    grid_out = fs.get(file_id)
    while chunk := grid_out.read(1024 * 1024):   # read in 1MB pieces
        out.write(chunk)

# Delete a file (removes from BOTH fs.files and fs.chunks)
fs.delete(file_id)

# Query metadata without downloading the file content
for grid_out in fs.find({"metadata.uploaded_by": "user_123"}):
    print(grid_out.filename, grid_out.length, grid_out.upload_date)
```

### Async version — Motor (matches your existing FastAPI/Motor coverage)

```python
import motor.motor_asyncio
import gridfs

client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
db = client["myapp"]
fs = motor.motor_asyncio.AsyncIOMotorGridFSBucket(db)

async def upload_file(file_bytes: bytes, filename: str):
    file_id = await fs.upload_from_stream(filename, file_bytes)
    return file_id

async def download_file(file_id):
    grid_out = await fs.open_download_stream(file_id)
    return await grid_out.read()
```

---

## GridFS vs S3 — the actual interview answer

| Factor | GridFS | S3 (or equivalent object storage) |
|---|---|---|
| **CDN/edge caching** | None — serves through your app/DB | Native (CloudFront/Cloudflare) |
| **Cost at scale** | Consumes your DB's storage/IOPS budget | Purpose-built, far cheaper per GB |
| **Query file metadata alongside app data** | Yes — same DB, can join in aggregation | Requires a separate metadata table/collection |
| **Durability/redundancy** | Only as good as your MongoDB replication setup | 11-nines durability built in |
| **Read/write path** | Round-trips through the MongoDB driver + app process | Direct presigned-URL upload/download, bypasses app server entirely |

**The one legitimate reason to reach for GridFS anyway:** you need to
**query files by their metadata using the same aggregation pipeline as the
rest of your app data** (e.g., "find all PDFs uploaded by users in this
segment, that also match this business-data filter" in one query) — GridFS
keeps file metadata queryable in the same database. For pure file storage
and serving, S3 + presigned URLs wins on cost, durability, and CDN
integration essentially every time.

---

## Interview Q&A

**Q: Why does MongoDB need GridFS instead of just storing a file in a document?**
A: MongoDB has a hard 16MB-per-document BSON limit. GridFS chunks a file into
255KB pieces across a `fs.chunks` collection, with metadata in `fs.files`,
sidestepping that limit for arbitrarily large files.

**Q: Would you recommend GridFS for a production file-upload feature?**
A: Almost never as the primary choice — S3 (or equivalent) plus presigned
URLs is cheaper, more durable, integrates with a CDN, and doesn't consume
your database's storage/IOPS. GridFS only makes sense when you specifically
need to query file metadata in the same aggregation pipeline as other
application data.

**Q: How do you avoid loading an entire large file into memory when serving it from GridFS?**
A: Stream it — read in fixed-size chunks (`grid_out.read(chunk_size)`) and
write incrementally, rather than calling `.read()` with no argument (which
loads the whole file into memory at once).

---

Related: `01_basics_installation_crud.md` (the 16MB BSON document limit this
solves), [17_storage_backends_s3.md](../../../00_Year0-2_Junior/07_Django_DRF/17_storage_backends_s3.md)
(the S3 alternative this compares against).
