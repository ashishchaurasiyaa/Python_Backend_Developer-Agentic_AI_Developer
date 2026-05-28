# 01 — File Uploads & Streaming

> Handle uploads efficiently: small files inline, large files chunked or direct-to-S3.

---

## Upload Sizes & Strategy

| Size | Strategy |
|---|---|
| < 1 MB | Inline POST, fine to buffer |
| 1-100 MB | Streamed POST or chunked upload |
| > 100 MB | Direct-to-S3 via presigned URL (file 02) |
| > 5 GB | Multipart S3 upload from client |

Never load entire 1 GB file into memory.

---

## FastAPI File Upload (Buffered)

```python
from fastapi import FastAPI, File, UploadFile

app = FastAPI()

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()  # entire file in memory!
    return {"filename": file.filename, "size": len(content)}
```

OK for small files. Bad for large.

---

## Streaming Upload (Recommended for Large)

Read in chunks; never load full file in memory.

```python
import aiofiles

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    save_path = f"/tmp/{file.filename}"
    async with aiofiles.open(save_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):   # 1 MB chunks
            await f.write(chunk)
    return {"size": os.path.getsize(save_path)}
```

Memory stays constant regardless of file size.

---

## Stream to S3 Directly

```python
import aioboto3

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    session = aioboto3.Session()
    async with session.client("s3") as s3:
        await s3.upload_fileobj(
            file.file,        # raw file object
            "my-bucket",
            file.filename
        )
    return {"url": f"https://my-bucket.s3.amazonaws.com/{file.filename}"}
```

`upload_fileobj` streams in 5MB parts.

---

## Multipart Upload via API Server (Antipattern at Scale)

Proxying large files through your server:
- Doubles bandwidth (client→server→S3).
- Latency added.
- Server bandwidth bottleneck.

**Use only for small files or when you need to inspect content (virus scan, etc.).**

For large files: presigned URL pattern (file 02).

---

## Validation

### File type
```python
import filetype

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    head = await file.read(264)  # filetype needs first 264 bytes
    await file.seek(0)
    kind = filetype.guess(head)
    if not kind or kind.mime not in ALLOWED_TYPES:
        raise HTTPException(415, "Unsupported file type")
    ...
```

Don't trust file extension — read the binary signature.

### Size limit
```python
MAX_SIZE = 100 * 1024 * 1024  # 100MB
total = 0
while chunk := await file.read(1024 * 1024):
    total += len(chunk)
    if total > MAX_SIZE:
        raise HTTPException(413, "File too large")
    await f.write(chunk)
```

Or at LB level (NGINX `client_max_body_size`).

### Virus scan
```python
import clamd

cd = clamd.ClamdNetworkSocket()
result = cd.instream(file.file)
if result["stream"][0] != "OK":
    raise HTTPException(400, f"Virus: {result['stream'][1]}")
```

---

## Chunked Upload (Resumable)

For large files / spotty networks: upload in chunks; resume from last successful chunk.

### Protocol
```
1. Client → POST /upload/init  {filename, size, hash}
   → returns upload_id
2. For each 5MB chunk i in 0..N:
   Client → PUT /upload/{upload_id}/chunk/{i}
   ← 200 OK
3. When all chunks done:
   Client → POST /upload/{upload_id}/complete
   ← 200 final URL
```

### Implementation
```python
@app.post("/upload/init")
async def init_upload(req: InitRequest):
    upload_id = str(uuid.uuid4())
    await redis.hset(f"upload:{upload_id}", mapping={
        "filename": req.filename,
        "size": req.size,
        "total_chunks": req.total_chunks,
        "received_chunks": "0"
    })
    return {"upload_id": upload_id}

@app.put("/upload/{upload_id}/chunk/{index}")
async def upload_chunk(upload_id: str, index: int, request: Request):
    chunk_dir = f"/tmp/uploads/{upload_id}"
    os.makedirs(chunk_dir, exist_ok=True)
    chunk_path = f"{chunk_dir}/{index:06d}"

    async with aiofiles.open(chunk_path, "wb") as f:
        async for chunk in request.stream():
            await f.write(chunk)

    await redis.hincrby(f"upload:{upload_id}", "received_chunks", 1)
    return {"received": True}

@app.post("/upload/{upload_id}/complete")
async def complete(upload_id: str):
    meta = await redis.hgetall(f"upload:{upload_id}")
    if int(meta["received_chunks"]) != int(meta["total_chunks"]):
        raise HTTPException(400, "Missing chunks")

    # Assemble
    chunk_dir = f"/tmp/uploads/{upload_id}"
    chunks = sorted(os.listdir(chunk_dir))
    final_path = f"/uploads/{upload_id}-{meta['filename']}"

    async with aiofiles.open(final_path, "wb") as out:
        for cname in chunks:
            async with aiofiles.open(f"{chunk_dir}/{cname}", "rb") as inp:
                while data := await inp.read(1024*1024):
                    await out.write(data)

    # Clean up
    shutil.rmtree(chunk_dir)
    await redis.delete(f"upload:{upload_id}")

    return {"url": f"/files/{upload_id}"}
```

### Tus.io protocol
Standard resumable upload protocol. `tusd` server in Go; clients in JS/iOS/Android. Drop-in solution.

---

## Multipart Form Parsing

```python
from fastapi import Form

@app.post("/upload-with-meta")
async def upload(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(None)
):
    ...
```

Multipart body parsed automatically.

---

## Streaming Download

For downloading large files without buffering:

```python
from fastapi.responses import StreamingResponse

async def file_iterator(file_path):
    async with aiofiles.open(file_path, "rb") as f:
        while chunk := await f.read(1024 * 1024):
            yield chunk

@app.get("/download/{file_id}")
async def download(file_id: str):
    path = get_file_path(file_id)
    return StreamingResponse(
        file_iterator(path),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=file.bin"}
    )
```

---

## Range Requests (Video Streaming)

Allow client to download portions (for HTML5 video, seek):

```python
from fastapi import Request, Header

@app.get("/video/{id}")
async def stream_video(id: str, range: str = Header(None)):
    file_size = os.path.getsize(path)
    start, end = 0, file_size - 1

    if range:
        m = re.match(r"bytes=(\d+)-(\d*)", range)
        start = int(m.group(1))
        if m.group(2):
            end = int(m.group(2))

    async def iter():
        async with aiofiles.open(path, "rb") as f:
            await f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk_size = min(1024 * 1024, remaining)
                data = await f.read(chunk_size)
                if not data: break
                yield data
                remaining -= len(data)

    return StreamingResponse(
        iter(),
        status_code=206,
        media_type="video/mp4",
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
        }
    )
```

In production: use NGINX `mp4` module or CloudFront, not Python.

---

## Server Configuration

### NGINX
```nginx
client_max_body_size 100M;
client_body_buffer_size 1M;
client_body_timeout 60s;
```

### Uvicorn
```bash
uvicorn app:app --limit-max-requests 1000 --timeout-keep-alive 30
```

### Gunicorn
```bash
gunicorn app:app -k uvicorn.workers.UvicornWorker --timeout 300
```

For long uploads, increase timeouts.

---

## Storage Backends

### Local disk
- Pros: Simple, fastest read/write.
- Cons: Single-server, ephemeral on containers, expensive to back up.
- Use: Development, small apps.

### NFS / EFS
- Pros: Multi-server access.
- Cons: Latency, complexity.
- Use: Shared workdirs.

### S3 / GCS / Azure Blob
- Pros: Infinite scale, cheap, durable, CDN-friendly.
- Cons: API-based access, network latency.
- Use: Production default.

### MinIO (S3-compatible self-hosted)
- Pros: S3 API, on-premise.
- Cons: Ops responsibility.

---

## Direct File Access vs Pre-Signed URL

### Through your server (proxy)
```
Client → API → S3 → API → Client
```
Pros: Auth check on every access; URL hiding.
Cons: API bandwidth bottleneck.

### Pre-signed URL
```
Client → API (returns signed URL) → S3 directly
```
Pros: No bandwidth on API.
Cons: URL is accessible by anyone holding it (use short TTL).

For large/long-lived files: pre-signed URL. (See file 02.)

---

## File Metadata Storage

```sql
CREATE TABLE files (
    id           UUID PRIMARY KEY,
    user_id      UUID,
    filename     TEXT,
    content_type TEXT,
    size_bytes   BIGINT,
    storage_key  TEXT,        -- S3 key
    checksum     TEXT,
    uploaded_at  TIMESTAMPTZ,
    deleted_at   TIMESTAMPTZ NULL
);
CREATE INDEX ON files(user_id, uploaded_at DESC);
```

Keep DB metadata; files in object storage.

---

## File Versioning

For "edit history" pattern:

```sql
CREATE TABLE file_versions (
    file_id        UUID,
    version        INT,
    storage_key    TEXT,
    size_bytes     BIGINT,
    uploaded_at    TIMESTAMPTZ,
    PRIMARY KEY (file_id, version)
);
```

S3 has native versioning — enable on bucket and you get this free.

---

## Soft Delete + Cleanup

Mark `deleted_at`. Background job deletes from S3 after grace period:

```python
async def cleanup_deleted_files():
    files = await db.fetch(
        "SELECT * FROM files WHERE deleted_at < now() - interval '30 days'"
    )
    for f in files:
        await s3.delete_object(Bucket=BUCKET, Key=f.storage_key)
        await db.execute("DELETE FROM files WHERE id = $1", f.id)
```

---

## Quota Management

```sql
CREATE TABLE user_quotas (
    user_id   UUID PRIMARY KEY,
    used_bytes BIGINT,
    limit_bytes BIGINT
);
```

Check before upload:
```python
quota = await get_quota(user.id)
if quota.used_bytes + file_size > quota.limit_bytes:
    raise HTTPException(413, "Quota exceeded")
```

Update after upload:
```python
await db.execute(
    "UPDATE user_quotas SET used_bytes = used_bytes + $1 WHERE user_id = $2",
    file_size, user.id
)
```

---

## Common Pitfalls

### 1. Loading entire file in memory
```python
content = await file.read()  # 5GB → OOM
```

### 2. No size check
Attacker uploads 100GB → disk full.

### 3. Trusting file extension
`evil.exe.jpg` — extension says jpg but binary is exe.

### 4. Storing in / serving from web root
`/uploads/<user-controlled-path>/file.html` → user uploads HTML → XSS.

### 5. No virus scan
PDF malware, embedded scripts.

### 6. Forgotten cleanup
Failed multi-part uploads accumulate in S3 → bills grow.

```python
# Cleanup orphan multipart uploads
s3.list_multipart_uploads(Bucket=BUCKET)
# Abort old ones
```

### 7. Not setting MIME type
Defaults to `application/octet-stream` → browsers force download for images.

### 8. CDN serves stale files
Cache for too long; user can't see updates. Use versioned URLs.

---

## TL;DR

- Small files: buffered upload OK.
- Medium files: stream in chunks.
- Large files: direct-to-S3 via presigned URL.
- Validate file type via binary signature.
- Resumable uploads via chunked protocol or tus.io.
- Range requests for video/large download.
- Object storage (S3) as default.
- Metadata in DB; bytes in object storage.
- Quotas, soft delete, cleanup jobs.
- Never trust filename or extension from client.
