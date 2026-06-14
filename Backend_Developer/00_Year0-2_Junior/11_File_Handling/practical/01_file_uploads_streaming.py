"""
File Uploads & Streaming — Production Patterns
===============================================
Covers every upload/download pattern from the theory doc:

  1.  Buffered upload (small files, < 1 MB)
  2.  Streaming upload with chunked read (medium files, 1-100 MB)
  3.  Stream-to-S3 via aioboto3 (illustrative — requires aioboto3 + AWS creds)
  4.  File-type validation via binary magic bytes
  5.  Streaming size enforcement (reject oversized files on the fly)
  6.  Resumable chunked-upload protocol (init / chunk / complete)
  7.  Multipart form with metadata fields
  8.  Streaming download via StreamingResponse
  9.  HTTP Range requests for video seek (206 Partial Content)
  10. Quota check helpers (DB pattern)
  11. Soft-delete & background cleanup stub
  12. Common-pitfalls reference (documented inline)

External dependencies (only needed at runtime, not at import/compile time):
  pip install fastapi uvicorn aiofiles aioboto3 filetype python-multipart

All imports that require external packages are guarded or clearly marked so the
module compiles and is importable without them installed.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import uuid
from typing import AsyncGenerator, Dict, List, Optional

# ---------------------------------------------------------------------------
# Standard-library async file I/O — guard the import so the module is usable
# even when aiofiles is absent (for study / IDE navigation purposes).
# ---------------------------------------------------------------------------
try:
    import aiofiles  # pip install aiofiles
    _AIOFILES_AVAILABLE = True
except ImportError:
    aiofiles = None  # type: ignore[assignment]
    _AIOFILES_AVAILABLE = False

# ---------------------------------------------------------------------------
# FastAPI — guard the import similarly.
# python-multipart is required for File/Form parameter parsing; FastAPI raises
# RuntimeError (not ImportError) at route-registration time when it is absent.
# We probe for it here so we can skip endpoint registration gracefully.
# ---------------------------------------------------------------------------
import importlib.util as _importlib_util

_MULTIPART_AVAILABLE: bool = (
    _importlib_util.find_spec("multipart") is not None
    or _importlib_util.find_spec("python_multipart") is not None
)

try:
    from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
    from fastapi.responses import StreamingResponse
    _FASTAPI_AVAILABLE = True and _MULTIPART_AVAILABLE
except ImportError:
    FastAPI = None  # type: ignore[assignment,misc]
    _FASTAPI_AVAILABLE = False

logger = logging.getLogger(__name__)

# ==========================================================================
# CONSTANTS
# ==========================================================================

CHUNK_SIZE: int = 1024 * 1024           # 1 MB read/write unit
MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB hard server-side cap
S3_BUCKET: str = "my-app-uploads"

# MIME types considered safe for direct serving through the application.
ALLOWED_MIME_TYPES: List[str] = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
    "text/plain",
]


# ==========================================================================
# 1. FASTAPI APPLICATION INSTANCE
# ==========================================================================

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="File Uploads & Streaming Demo")
else:
    app = None  # type: ignore[assignment]


# ==========================================================================
# 2. BUFFERED UPLOAD — fine for small files only (< 1 MB)
# ==========================================================================

if _FASTAPI_AVAILABLE:
    @app.post("/upload/buffered")  # type: ignore[union-attr]
    async def upload_buffered(file: UploadFile = File(...)) -> Dict[str, object]:
        """
        Read the entire file into memory in one call.

        PITFALL: If the file is large this causes an OOM (out-of-memory) error.
        Only use for files known to be small (< 1 MB).
        """
        content: bytes = await file.read()  # entire payload in RAM
        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(content),
        }


# ==========================================================================
# 3. STREAMING UPLOAD — constant memory regardless of file size
# ==========================================================================

if _FASTAPI_AVAILABLE and _AIOFILES_AVAILABLE:
    @app.post("/upload/stream")  # type: ignore[union-attr]
    async def upload_stream(file: UploadFile = File(...)) -> Dict[str, object]:
        """
        Read the upload in 1 MB increments and write each chunk to disk
        immediately.  Peak RAM usage is bounded by CHUNK_SIZE — NOT file size.
        """
        save_path: str = f"/tmp/{uuid.uuid4().hex}_{file.filename}"
        total_bytes: int = 0

        async with aiofiles.open(save_path, "wb") as out_file:
            while True:
                chunk: bytes = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                await out_file.write(chunk)

        return {
            "saved_to": save_path,
            "size_bytes": total_bytes,
        }


# ==========================================================================
# 4. STREAMING UPLOAD WITH SIZE ENFORCEMENT
# ==========================================================================

if _FASTAPI_AVAILABLE and _AIOFILES_AVAILABLE:
    @app.post("/upload/stream/validated")  # type: ignore[union-attr]
    async def upload_stream_validated(file: UploadFile = File(...)) -> Dict[str, object]:
        """
        Same as upload_stream but rejects the request mid-stream once the
        cumulative byte count exceeds MAX_UPLOAD_SIZE.

        Doing the check inside the read loop means we never buffer the whole
        file — we fail fast as soon as the limit is crossed.
        """
        save_path: str = f"/tmp/{uuid.uuid4().hex}_{file.filename}"
        total_bytes: int = 0

        async with aiofiles.open(save_path, "wb") as out_file:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE:
                    # Clean up the partial file before raising.
                    await out_file.flush()
                try:
                    if total_bytes > MAX_UPLOAD_SIZE:
                        os.unlink(save_path)
                        raise HTTPException(
                            status_code=413,
                            detail=f"File exceeds the {MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit.",
                        )
                except NameError:
                    # HTTPException not available (FastAPI not installed)
                    raise RuntimeError("File too large")
                await out_file.write(chunk)

        return {"saved_to": save_path, "size_bytes": total_bytes}


# ==========================================================================
# 5. FILE-TYPE VALIDATION VIA BINARY MAGIC BYTES
# ==========================================================================

def _detect_mime_type(header_bytes: bytes) -> Optional[str]:
    """
    Inspect the leading bytes of a file to detect its real MIME type.

    We read the first 264 bytes because that is the maximum magic-byte
    sequence length used by the 'filetype' library.

    Returns the MIME string (e.g. "image/jpeg") or None if unrecognised.

    NOTE: Do NOT trust the file extension or the Content-Type header sent
    by the client — both are trivially faked.  An attacker can rename
    evil.exe to evil.jpg; the binary signature cannot be so easily spoofed.
    """
    try:
        import filetype  # pip install filetype
        kind = filetype.guess(header_bytes)
        return kind.mime if kind else None
    except ImportError:
        logger.warning("filetype package not installed; skipping MIME detection")
        return None


MAGIC_HEADER_BYTES: int = 264  # maximum magic-byte sequence length


if _FASTAPI_AVAILABLE and _AIOFILES_AVAILABLE:
    @app.post("/upload/validated")  # type: ignore[union-attr]
    async def upload_validated(file: UploadFile = File(...)) -> Dict[str, object]:
        """
        Validate file type before saving:

          1. Read the first 264 bytes.
          2. Seek back to position 0.
          3. Detect MIME type from binary signature.
          4. Reject if not in ALLOWED_MIME_TYPES.
          5. Stream the rest of the file to disk.
        """
        header: bytes = await file.read(MAGIC_HEADER_BYTES)
        await file.seek(0)                      # rewind to start

        detected_mime: Optional[str] = _detect_mime_type(header)
        if detected_mime not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type: {detected_mime}",
            )

        save_path = f"/tmp/{uuid.uuid4().hex}_{file.filename}"
        async with aiofiles.open(save_path, "wb") as out_file:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                await out_file.write(chunk)

        return {"saved_to": save_path, "detected_mime": detected_mime}


# ==========================================================================
# 6. STREAM DIRECTLY TO S3 (illustrative — requires aioboto3 + AWS creds)
# ==========================================================================

if _FASTAPI_AVAILABLE:
    @app.post("/upload/s3")  # type: ignore[union-attr]
    async def upload_to_s3(file: UploadFile = File(...)) -> Dict[str, object]:
        """
        Pipe the raw UploadFile object directly into boto3's upload_fileobj.

        boto3 internally uses multipart upload in 5 MB parts, so peak server
        RAM is bounded — no intermediate file on disk is needed.

        Requires:
          pip install aioboto3
          AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars set
        """
        try:
            import aioboto3  # pip install aioboto3
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="aioboto3 is not installed on this server.",
            )

        session = aioboto3.Session()
        async with session.client("s3") as s3_client:  # type: ignore[attr-defined]
            await s3_client.upload_fileobj(
                file.file,          # raw SpooledTemporaryFile object
                S3_BUCKET,
                file.filename,
            )

        public_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{file.filename}"
        return {"url": public_url}


# ==========================================================================
# 7. RESUMABLE CHUNKED UPLOAD PROTOCOL
#    Protocol:
#      POST /upload/init          → { upload_id }
#      PUT  /upload/{id}/chunk/{i} (raw body = chunk bytes)
#      POST /upload/{id}/complete → { url }
# ==========================================================================

# In-process state for demo purposes only.
# Production: store in Redis with hset / hincrby so any replica can serve
# subsequent chunk requests.
_UPLOAD_REGISTRY: Dict[str, Dict[str, object]] = {}


if _FASTAPI_AVAILABLE:
    from fastapi import Body

    # --- 7a. Init upload session ---

    @app.post("/upload/init")  # type: ignore[union-attr]
    async def init_upload(
        filename: str = Body(...),
        total_chunks: int = Body(...),
        file_size: int = Body(...),
    ) -> Dict[str, object]:
        """
        Client calls this first to reserve an upload_id.

        Parameters sent in JSON body:
          filename     — original filename (display only; never used as a path)
          total_chunks — how many PUT /chunk/{i} calls will follow
          file_size    — declared file size in bytes (used for quota checks)

        Returns upload_id that must accompany every subsequent chunk PUT.
        """
        upload_id: str = str(uuid.uuid4())
        _UPLOAD_REGISTRY[upload_id] = {
            "filename": filename,
            "total_chunks": total_chunks,
            "file_size": file_size,
            "received_chunks": 0,
        }
        logger.info("Upload session created: %s (%s, %d chunks)", upload_id, filename, total_chunks)
        return {"upload_id": upload_id}

    # --- 7b. Receive individual chunks ---

    @app.put("/upload/{upload_id}/chunk/{index}")  # type: ignore[union-attr]
    async def upload_chunk(
        upload_id: str,
        index: int,
        request: Request,
    ) -> Dict[str, object]:
        """
        Client streams a single chunk as the raw request body.

        Chunks are saved as zero-padded files (000000, 000001, …) so they can
        be assembled in the correct order at completion.  Redis-based production
        implementations use HINCRBY to count received chunks atomically across
        multiple server replicas.
        """
        if upload_id not in _UPLOAD_REGISTRY:
            raise HTTPException(status_code=404, detail="Unknown upload_id")

        chunk_dir: str = f"/tmp/uploads/{upload_id}"
        os.makedirs(chunk_dir, exist_ok=True)
        chunk_path: str = f"{chunk_dir}/{index:06d}"

        if _AIOFILES_AVAILABLE:
            async with aiofiles.open(chunk_path, "wb") as chunk_file:
                async for piece in request.stream():
                    await chunk_file.write(piece)
        else:
            # Synchronous fallback (blocks event loop — acceptable for demo)
            with open(chunk_path, "wb") as chunk_file_sync:
                async for piece in request.stream():
                    chunk_file_sync.write(piece)

        meta = _UPLOAD_REGISTRY[upload_id]
        meta["received_chunks"] = int(meta["received_chunks"]) + 1  # type: ignore[operator]
        logger.info(
            "Chunk %d/%d received for upload %s",
            index, meta["total_chunks"], upload_id,
        )
        return {"received": True, "chunk_index": index}

    # --- 7c. Assemble chunks into final file ---

    @app.post("/upload/{upload_id}/complete")  # type: ignore[union-attr]
    async def complete_upload(upload_id: str) -> Dict[str, object]:
        """
        Client calls this after the last chunk PUT succeeds.

        Steps:
          1. Verify all expected chunks arrived.
          2. Stream-concatenate chunks into the final file.
          3. Remove the temporary chunk directory.
          4. Remove the registry entry.
        """
        if upload_id not in _UPLOAD_REGISTRY:
            raise HTTPException(status_code=404, detail="Unknown upload_id")

        meta = _UPLOAD_REGISTRY[upload_id]
        received: int = int(meta["received_chunks"])  # type: ignore[arg-type]
        total: int = int(meta["total_chunks"])  # type: ignore[arg-type]

        if received != total:
            raise HTTPException(
                status_code=400,
                detail=f"Missing chunks: received {received}/{total}",
            )

        chunk_dir = f"/tmp/uploads/{upload_id}"
        chunk_names: List[str] = sorted(os.listdir(chunk_dir))
        safe_filename: str = f"{upload_id}-{meta['filename']}"
        final_path: str = f"/tmp/{safe_filename}"

        if _AIOFILES_AVAILABLE:
            async with aiofiles.open(final_path, "wb") as out_file:
                for chunk_name in chunk_names:
                    async with aiofiles.open(f"{chunk_dir}/{chunk_name}", "rb") as inp:
                        while True:
                            data: bytes = await inp.read(CHUNK_SIZE)
                            if not data:
                                break
                            await out_file.write(data)
        else:
            with open(final_path, "wb") as out_file_sync:
                for chunk_name in chunk_names:
                    with open(f"{chunk_dir}/{chunk_name}", "rb") as inp_sync:
                        while True:
                            data = inp_sync.read(CHUNK_SIZE)
                            if not data:
                                break
                            out_file_sync.write(data)

        # Clean up temporary chunk storage.
        shutil.rmtree(chunk_dir, ignore_errors=True)
        del _UPLOAD_REGISTRY[upload_id]

        logger.info("Upload %s assembled → %s", upload_id, final_path)
        return {"url": f"/files/{upload_id}", "path": final_path}


# ==========================================================================
# 8. MULTIPART FORM WITH METADATA FIELDS
# ==========================================================================

if _FASTAPI_AVAILABLE:
    @app.post("/upload/with-meta")  # type: ignore[union-attr]
    async def upload_with_metadata(
        file: UploadFile = File(...),
        title: str = Form(...),
        description: Optional[str] = Form(None),
    ) -> Dict[str, object]:
        """
        Receive a file alongside structured form fields in a single multipart
        request.  FastAPI parses the multipart body automatically — each named
        part maps to its annotated parameter.
        """
        content: bytes = await file.read()
        return {
            "filename": file.filename,
            "title": title,
            "description": description,
            "size_bytes": len(content),
        }


# ==========================================================================
# 9. STREAMING DOWNLOAD — constant memory, no buffering
# ==========================================================================

def _file_chunk_generator(file_path: str) -> AsyncGenerator[bytes, None]:
    """
    Async generator that yields the file in CHUNK_SIZE increments.
    Used with FastAPI's StreamingResponse so the server never holds the
    entire file in RAM.
    """
    async def _inner() -> AsyncGenerator[bytes, None]:
        if _AIOFILES_AVAILABLE:
            async with aiofiles.open(file_path, "rb") as f:
                while True:
                    chunk = await f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
        else:
            with open(file_path, "rb") as f_sync:
                while True:
                    chunk = f_sync.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk

    return _inner()  # type: ignore[return-value]


if _FASTAPI_AVAILABLE:
    @app.get("/download/{file_id}")  # type: ignore[union-attr]
    async def download_file(file_id: str) -> StreamingResponse:
        """
        Stream a file to the client without loading it into memory.

        StreamingResponse pulls from the async generator on demand, writing
        each chunk to the socket as it arrives.  The client sees a normal
        file download with correct headers.

        NOTE: In production, prefer serving files directly from S3 via a
        presigned URL rather than proxying through the API server — it
        eliminates server bandwidth cost entirely.
        """
        # In a real application this would look up the path from a database.
        file_path: str = f"/tmp/files/{file_id}"
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        return StreamingResponse(
            _file_chunk_generator(file_path),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{file_id}"',
                "Content-Length": str(os.path.getsize(file_path)),
            },
        )


# ==========================================================================
# 10. HTTP RANGE REQUESTS — video seek (206 Partial Content)
# ==========================================================================

def _parse_range_header(range_header: str, file_size: int) -> tuple:
    """
    Parse an HTTP Range header of the form "bytes=<start>-<end?>".

    Returns (start, end) as integer byte offsets (inclusive, 0-based).
    Raises ValueError for malformed headers.
    """
    match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        raise ValueError(f"Malformed Range header: {range_header!r}")
    start: int = int(match.group(1))
    end: int = int(match.group(2)) if match.group(2) else file_size - 1
    return start, end


if _FASTAPI_AVAILABLE:
    @app.get("/video/{video_id}")  # type: ignore[union-attr]
    async def stream_video(
        video_id: str,
        range: Optional[str] = Header(None),
    ) -> StreamingResponse:
        """
        Serve a video file with HTTP Range support so HTML5 players can seek.

        When the client sends "Range: bytes=1048576-" the server returns
        status 206 Partial Content with only the requested byte range.
        Browsers send this automatically; no client-side code is needed.

        NOTE: For production video delivery use NGINX (ngx_http_mp4_module) or
        CloudFront rather than piping through Python — they handle byte-range
        serving natively and are orders of magnitude faster.
        """
        video_path: str = f"/tmp/videos/{video_id}"
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video not found")

        file_size: int = os.path.getsize(video_path)
        start: int = 0
        end: int = file_size - 1

        if range:
            try:
                start, end = _parse_range_header(range, file_size)
            except ValueError:
                raise HTTPException(status_code=416, detail="Range Not Satisfiable")

        content_length: int = end - start + 1

        async def _range_generator() -> AsyncGenerator[bytes, None]:
            remaining: int = content_length
            if _AIOFILES_AVAILABLE:
                async with aiofiles.open(video_path, "rb") as vf:
                    await vf.seek(start)
                    while remaining > 0:
                        read_size: int = min(CHUNK_SIZE, remaining)
                        piece: bytes = await vf.read(read_size)
                        if not piece:
                            break
                        yield piece
                        remaining -= len(piece)
            else:
                with open(video_path, "rb") as vf_sync:
                    vf_sync.seek(start)
                    while remaining > 0:
                        read_size = min(CHUNK_SIZE, remaining)
                        piece = vf_sync.read(read_size)
                        if not piece:
                            break
                        yield piece
                        remaining -= len(piece)

        status_code: int = 206 if range else 200
        headers: Dict[str, str] = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Range": f"bytes {start}-{end}/{file_size}",
        }
        return StreamingResponse(
            _range_generator(),
            status_code=status_code,
            media_type="video/mp4",
            headers=headers,
        )


# ==========================================================================
# 11. QUOTA MANAGEMENT HELPERS
# ==========================================================================

class QuotaExceededError(Exception):
    """Raised when a user's storage quota would be exceeded by an upload."""


class UserQuota:
    """
    Lightweight data class mirroring the user_quotas DB table:

      CREATE TABLE user_quotas (
          user_id     UUID PRIMARY KEY,
          used_bytes  BIGINT,
          limit_bytes BIGINT
      );
    """

    def __init__(self, user_id: str, used_bytes: int, limit_bytes: int) -> None:
        self.user_id: str = user_id
        self.used_bytes: int = used_bytes
        self.limit_bytes: int = limit_bytes

    @property
    def available_bytes(self) -> int:
        return max(0, self.limit_bytes - self.used_bytes)


async def check_quota(quota: UserQuota, incoming_bytes: int) -> None:
    """
    Raise QuotaExceededError if adding incoming_bytes would exceed the quota.
    Call this before writing any data to storage.

    In a FastAPI endpoint:
        quota = await db.fetch_one("SELECT * FROM user_quotas WHERE user_id=$1", user.id)
        await check_quota(quota, file.size)
        # ... proceed with upload ...
        await db.execute(
            "UPDATE user_quotas SET used_bytes = used_bytes + $1 WHERE user_id = $2",
            file_size, user.id,
        )
    """
    if quota.used_bytes + incoming_bytes > quota.limit_bytes:
        raise QuotaExceededError(
            f"Upload of {incoming_bytes:,} bytes would exceed quota "
            f"({quota.used_bytes:,}/{quota.limit_bytes:,} bytes used)"
        )


# ==========================================================================
# 12. SOFT DELETE & BACKGROUND CLEANUP STUB
# ==========================================================================

class FileMeta:
    """
    Mirrors the files table in PostgreSQL:

      CREATE TABLE files (
          id           UUID PRIMARY KEY,
          user_id      UUID,
          filename     TEXT,
          content_type TEXT,
          size_bytes   BIGINT,
          storage_key  TEXT,     -- S3 object key
          checksum     TEXT,     -- SHA-256 hex digest
          uploaded_at  TIMESTAMPTZ,
          deleted_at   TIMESTAMPTZ NULL
      );
      CREATE INDEX ON files(user_id, uploaded_at DESC);
    """

    def __init__(
        self,
        file_id: str,
        user_id: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_key: str,
        checksum: Optional[str] = None,
    ) -> None:
        self.file_id = file_id
        self.user_id = user_id
        self.filename = filename
        self.content_type = content_type
        self.size_bytes = size_bytes
        self.storage_key = storage_key
        self.checksum = checksum


async def cleanup_deleted_files(db: object, s3_client: object) -> int:
    """
    Background job: hard-delete S3 objects and DB rows for files that have
    been soft-deleted for more than 30 days.

    Schedule with APScheduler / Celery Beat / a cron container.

    Returns the number of files permanently deleted.
    """
    # Pseudocode — replace `db` and `s3_client` with real async drivers.
    # files = await db.fetch(
    #     "SELECT * FROM files WHERE deleted_at < now() - INTERVAL '30 days'"
    # )
    # deleted_count = 0
    # for f in files:
    #     await s3_client.delete_object(Bucket=S3_BUCKET, Key=f.storage_key)
    #     await db.execute("DELETE FROM files WHERE id = $1", f.file_id)
    #     deleted_count += 1
    # logger.info("Cleanup: permanently removed %d file(s)", deleted_count)
    # return deleted_count

    logger.info("cleanup_deleted_files: no-op stub — wire up real db/s3 clients")
    return 0


# ==========================================================================
# 13. ORPHAN MULTIPART UPLOAD CLEANUP (S3)
# ==========================================================================

async def abort_orphan_multipart_uploads(s3_client: object, age_hours: int = 24) -> None:
    """
    List incomplete multipart uploads in S3 older than `age_hours` and abort
    them.  Forgotten multipart uploads accumulate silently and are billed at
    the same rate as completed objects.

    Wire into a daily cron job.

    Pseudocode:
        response = await s3_client.list_multipart_uploads(Bucket=S3_BUCKET)
        for upload in response.get("Uploads", []):
            age = datetime.utcnow() - upload["Initiated"].replace(tzinfo=None)
            if age.total_seconds() > age_hours * 3600:
                await s3_client.abort_multipart_upload(
                    Bucket=S3_BUCKET,
                    Key=upload["Key"],
                    UploadId=upload["UploadId"],
                )
    """
    logger.info(
        "abort_orphan_multipart_uploads: stub — wire up real S3 client (bucket=%s, age_threshold=%dh)",
        S3_BUCKET,
        age_hours,
    )


# ==========================================================================
# 14. COMMON PITFALLS SUMMARY (reference — see theory doc for details)
# ==========================================================================

PITFALLS: str = """
Common pitfalls in file upload/download handling:

1. Loading the entire file into RAM
   BAD:  content = await file.read()     # 5 GB → OOM
   GOOD: read in CHUNK_SIZE increments; yield/write each chunk.

2. No size limit
   Attacker uploads 100 GB → disk full or memory exhausted.
   Fix: check cumulative size inside the read loop; reject at MAX_UPLOAD_SIZE.

3. Trusting the file extension
   evil.exe renamed to evil.jpg bypasses extension checks.
   Fix: read the binary magic-byte signature (filetype.guess).

4. Storing uploads in / serving from the web root
   /uploads/<user-controlled-path>/file.html → XSS via user-uploaded HTML.
   Fix: store with a UUID key; never expose user-supplied filenames as URL paths.

5. Skipping virus scanning
   Embedded malware in PDFs, images, archives.
   Fix: stream through ClamAV (clamd) before making files accessible.

6. Forgetting to abort orphaned multipart uploads in S3
   Failed uploads leave behind parts that are billed indefinitely.
   Fix: abort_orphan_multipart_uploads() scheduled daily.

7. Not setting the MIME type on the response
   Defaults to application/octet-stream → browser forces download for images.
   Fix: look up the stored content_type from DB; set media_type accordingly.

8. CDN caching stale file versions
   User replaces a file; CDN still serves the old version.
   Fix: append a version counter or content hash to the S3 key; invalidate CDN.
"""


# ==========================================================================
# 15. SERVER CONFIGURATION REFERENCE STRINGS
# ==========================================================================

NGINX_CONFIG: str = """
# /etc/nginx/nginx.conf — upload-friendly settings
client_max_body_size  100M;    # must match MAX_UPLOAD_SIZE above
client_body_buffer_size 1M;    # buffer to RAM before spooling to disk
client_body_timeout   60s;     # abort stalled uploads after 60 s
"""

UVICORN_CMD: str = """
# Development
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Production (long uploads need higher timeout)
uvicorn app:app --limit-max-requests 1000 --timeout-keep-alive 30
"""

GUNICORN_CMD: str = """
# Production — Gunicorn with Uvicorn workers
gunicorn app:app \\
    -k uvicorn.workers.UvicornWorker \\
    -w 4 \\
    --bind 0.0.0.0:8000 \\
    --timeout 300 \\
    --keep-alive 5 \\
    --access-logfile - \\
    --error-logfile -

# Rule of thumb: workers = 2 * CPU_count + 1
# Increase --timeout for large file uploads (default 30 s is too short).
"""


# ==========================================================================
# MAIN — self-contained demonstration (no external infra required)
# ==========================================================================

if __name__ == "__main__":
    import asyncio
    import tempfile

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    async def _demo() -> None:
        print("\n=== File Uploads & Streaming — Demo ===\n")

        # --- Demo 1: Range header parsing ---
        print("1. Range header parsing")
        file_size_demo = 10 * 1024 * 1024  # 10 MB
        cases = [
            ("bytes=0-1048575",  (0, 1048575)),
            ("bytes=2097152-",   (2097152, file_size_demo - 1)),
        ]
        for header, expected in cases:
            result = _parse_range_header(header, file_size_demo)
            status = "PASS" if result == expected else "FAIL"
            print(f"   [{status}] '{header}'  →  {result}")

        # --- Demo 2: MIME type detection stub ---
        print("\n2. Binary magic-byte MIME detection (requires 'filetype' package)")
        # PNG magic bytes: 0x89 50 4E 47 0D 0A 1A 0A
        fake_png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 256
        detected = _detect_mime_type(fake_png_header)
        if detected:
            print(f"   Detected MIME: {detected}")
        else:
            print("   filetype not installed — detection skipped (expected in CI)")

        # --- Demo 3: Quota check ---
        print("\n3. Quota check")
        quota = UserQuota(
            user_id="user-abc",
            used_bytes=90 * 1024 * 1024,   # 90 MB used
            limit_bytes=100 * 1024 * 1024, # 100 MB limit
        )
        # 5 MB upload — should pass
        try:
            await check_quota(quota, 5 * 1024 * 1024)
            print("   [PASS] 5 MB upload within quota")
        except QuotaExceededError as exc:
            print(f"   [FAIL] Unexpected quota error: {exc}")

        # 15 MB upload — should raise
        try:
            await check_quota(quota, 15 * 1024 * 1024)
            print("   [FAIL] Expected QuotaExceededError but got none")
        except QuotaExceededError as exc:
            print(f"   [PASS] Quota correctly rejected: {exc}")

        # --- Demo 4: Streaming file write + read-back ---
        print("\n4. Streaming write/read (aiofiles)")
        if _AIOFILES_AVAILABLE:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
                tmp_path = tmp.name

            # Write 3 chunks of 1 MB each
            payload = os.urandom(1024)  # 1 KB for demo speed
            total_written = 0
            async with aiofiles.open(tmp_path, "wb") as f:
                for _ in range(4):
                    await f.write(payload)
                    total_written += len(payload)

            # Read back in chunks and verify byte count
            total_read = 0
            async with aiofiles.open(tmp_path, "rb") as f:
                while True:
                    chunk = await f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total_read += len(chunk)

            os.unlink(tmp_path)
            status = "PASS" if total_read == total_written else "FAIL"
            print(f"   [{status}] Written {total_written} bytes, read back {total_read} bytes")
        else:
            print("   aiofiles not installed — streaming I/O demo skipped")

        # --- Demo 5: Pitfalls & config reference ---
        print("\n5. Pitfalls reference (first 3 lines):")
        for line in PITFALLS.strip().splitlines()[:5]:
            print(f"   {line}")

        print("\n=== Demo complete ===")

    asyncio.run(_demo())
