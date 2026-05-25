# File Upload API Design

## Why It Matters

File uploads = special case requiring careful API design:
- **Size** — small (avatar) vs huge (video)
- **Reliability** — resumable for mobile
- **Security** — validate, scan, sandbox
- **Performance** — direct-to-storage vs proxy

Senior interview: "Mobile app uploads 500MB video on flaky network — design."

---

## Upload Patterns

### Pattern 1: Direct Multipart (Small Files <10MB)

```http
POST /uploads
Content-Type: multipart/form-data

------boundary
Content-Disposition: form-data; name="file"; filename="avatar.jpg"
Content-Type: image/jpeg

<binary>
------boundary
Content-Disposition: form-data; name="title"

My Avatar
------boundary--
```

Server receives, validates, stores. Simple, works for small files.

### Pattern 2: Pre-signed URL (Medium/Large 10MB-5GB)

```
1. Client → Backend: POST /uploads/init {filename, size, content_type}
2. Backend → Storage: generate presigned PUT URL
3. Backend → Client: {upload_url, key, expires}
4. Client → Storage: PUT directly (large bytes don't touch backend)
5. Client → Backend: POST /uploads/complete {key}
6. Backend: verify, create DB record, scan, etc.
```

Saves backend bandwidth + memory + time.

### Pattern 3: Multipart S3 Upload (Very Large >5GB / Resumable)

```
1. Client → Backend: POST /uploads/multipart/init {filename, size}
2. Backend → S3: CreateMultipartUpload → upload_id
3. Backend → Client: {upload_id, part_size, parts: [presigned URLs]}
4. Client uploads parts in parallel (with retries)
5. Client → Backend: POST /uploads/multipart/complete {upload_id, parts: [{Etag, PartNumber}]}
6. Backend → S3: CompleteMultipartUpload
```

Resumable: retries individual parts on failure.

### Pattern 4: Chunked + Resumable (Custom Implementation)

```
Client tracks bytes_uploaded.
POST /uploads/chunked/init → {upload_session_id, chunk_size}

For each chunk:
PUT /uploads/chunked/{session_id}?offset=N
   Content-Length: chunk_size
   <chunk bytes>

If failure, client resumes from last successful offset:
GET /uploads/chunked/{session_id}/status → {bytes_received}
```

More control than S3 multipart; rarely needed.

### Pattern 5: tus Protocol (Open Standard)

```
POST /files → 201 Created + Location: /files/abc

For each chunk:
PATCH /files/abc
   Upload-Offset: 0
   Content-Type: application/offset+octet-stream
   Content-Length: chunk_size

Check status:
HEAD /files/abc → Upload-Offset: 12345
```

`tus.io` — standardized resumable upload protocol.

---

## Validation Pipeline

```python
def validate_upload(file: UploadFile, max_size: int, allowed_types: set):
    # 1. Size check
    if file.size > max_size:
        raise HTTPException(413, 'File too large')

    # 2. Real MIME via libmagic (not just extension/header)
    head = file.read(2048)
    file.seek(0)
    detected_mime = magic.from_buffer(head, mime=True)
    if detected_mime not in allowed_types:
        raise HTTPException(415, f'Unsupported type: {detected_mime}')

    # 3. Extension match
    if not _ext_matches_mime(file.filename, detected_mime):
        raise HTTPException(400, 'Extension/content mismatch')

    # 4. Filename sanitization
    safe_name = sanitize_filename(file.filename)

    return safe_name, detected_mime
```

### Image-Specific

```python
from PIL import Image

Image.MAX_IMAGE_PIXELS = 100_000_000   # 100MP cap — prevent decompression bombs

def validate_image(file):
    try:
        img = Image.open(file)
        img.verify()
    except Exception:
        raise HTTPException(400, 'Invalid image')

    file.seek(0)
    img = Image.open(file)
    if img.width > 4000 or img.height > 4000:
        raise HTTPException(400, 'Dimensions too large')
    file.seek(0)
```

### Filename Sanitization

```python
import re
import os
from uuid import uuid4


def sanitize_filename(name: str) -> str:
    # Strip path components
    name = os.path.basename(name)
    # Remove dangerous chars
    name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    # Truncate
    return name[:200]


def safe_storage_path(user_id: int, filename: str) -> str:
    """UUID-based path — no client-controlled paths."""
    safe = sanitize_filename(filename)
    return f'uploads/{user_id}/{uuid4()}/{safe}'
```

---

## Security

### MIME Spoofing Prevention

```python
# Client claims Content-Type: image/jpeg but uploads malicious.exe
# libmagic detects actual content
import magic

actual_mime = magic.from_buffer(file.read(2048), mime=True)
file.seek(0)
if actual_mime != claimed_mime:
    raise HTTPException(400, 'Content type mismatch')
```

### Virus Scanning (Async)

```python
@shared_task
def scan_for_viruses(doc_id):
    doc = Document.objects.get(id=doc_id)
    doc.scan_status = 'scanning'
    doc.save()

    # ClamAV
    result = subprocess.run(['clamdscan', '--no-summary', doc.local_path], capture_output=True)

    if result.returncode == 0:
        doc.scan_status = 'clean'
    elif result.returncode == 1:
        doc.scan_status = 'infected'
        # Move to quarantine, alert
        quarantine(doc)
    else:
        doc.scan_status = 'failed'

    doc.save()


# Mark file "pending scan" → block access until clean
```

### Sandbox Storage

- Different bucket/folder per tenant
- IAM least-privilege (write-only role for uploads)
- Versioning enabled (recover from malicious overwrites)
- Lifecycle: auto-delete old/pending files
- Encryption (SSE-S3 or SSE-KMS)

### Block Executable Extensions

```python
DENIED_EXTENSIONS = {'.exe', '.bat', '.cmd', '.sh', '.ps1', '.app', '.dmg'}


if any(filename.lower().endswith(ext) for ext in DENIED_EXTENSIONS):
    raise HTTPException(415, 'File type not allowed')
```

---

## Resumable Upload Implementation

### Server-Side Session

```python
class UploadSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    total_size = models.BigIntegerField()
    chunk_size = models.IntegerField(default=5 * 1024 * 1024)
    received_bytes = models.BigIntegerField(default=0)
    s3_upload_id = models.CharField(max_length=200)
    parts = models.JSONField(default=list)
    status = models.CharField(max_length=20, default='active')
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
```

### Endpoints

```python
@app.post('/uploads/multipart/init')
async def init_multipart(filename: str, size: int, content_type: str, user=Depends(get_user)):
    if size > 5 * 1024 * 1024 * 1024:   # 5GB
        raise HTTPException(413)

    key = f'uploads/{user.id}/{uuid4()}/{sanitize_filename(filename)}'

    # Initiate S3 multipart
    client = boto3.client('s3')
    resp = client.create_multipart_upload(
        Bucket='my-bucket',
        Key=key,
        ContentType=content_type,
        ServerSideEncryption='AES256',
    )

    session = UploadSession.objects.create(
        user=user,
        filename=filename,
        total_size=size,
        s3_upload_id=resp['UploadId'],
        expires_at=timezone.now() + timedelta(hours=24),
    )

    return {
        'session_id': str(session.id),
        'upload_id': resp['UploadId'],
        'key': key,
        'chunk_size': 5 * 1024 * 1024,
        'expires_at': session.expires_at.isoformat(),
    }


@app.post('/uploads/multipart/{session_id}/part/{part_number}/url')
async def get_part_url(session_id, part_number, user=Depends(get_user)):
    session = UploadSession.objects.get(id=session_id, user=user)

    client = boto3.client('s3')
    url = client.generate_presigned_url(
        'upload_part',
        Params={
            'Bucket': 'my-bucket',
            'Key': session.key,
            'UploadId': session.s3_upload_id,
            'PartNumber': part_number,
        },
        ExpiresIn=3600,
    )
    return {'url': url}


@app.post('/uploads/multipart/{session_id}/complete')
async def complete_multipart(session_id, parts: list[dict], user=Depends(get_user)):
    """parts = [{'ETag': '...', 'PartNumber': 1}, ...]"""
    session = UploadSession.objects.get(id=session_id, user=user)

    client = boto3.client('s3')
    client.complete_multipart_upload(
        Bucket='my-bucket',
        Key=session.key,
        UploadId=session.s3_upload_id,
        MultipartUpload={'Parts': parts},
    )

    session.status = 'completed'
    session.save()

    # Create document record
    doc = Document.objects.create(
        user=user,
        filename=session.filename,
        s3_key=session.key,
        size=session.total_size,
        scan_status='pending',
    )

    # Async virus scan
    scan_for_viruses.delay(doc.id)

    return {'document_id': doc.id}


@app.post('/uploads/multipart/{session_id}/abort')
async def abort_multipart(session_id, user=Depends(get_user)):
    session = UploadSession.objects.get(id=session_id, user=user)

    client = boto3.client('s3')
    client.abort_multipart_upload(
        Bucket='my-bucket',
        Key=session.key,
        UploadId=session.s3_upload_id,
    )

    session.status = 'aborted'
    session.save()
    return {'aborted': True}
```

---

## Cleanup

### Lifecycle (S3)

```json
{
    "Rules": [
        {
            "ID": "abort-incomplete-multipart",
            "Status": "Enabled",
            "AbortIncompleteMultipartUpload": { "DaysAfterInitiation": 7 }
        },
        {
            "ID": "expire-pending-uploads",
            "Status": "Enabled",
            "Filter": { "Prefix": "uploads/" },
            "Expiration": { "Days": 30 }
        }
    ]
}
```

### Orphan Cleanup Job

```python
@shared_task
def cleanup_expired_sessions():
    expired = UploadSession.objects.filter(
        expires_at__lt=timezone.now(),
        status='active',
    )
    for session in expired:
        # Abort S3 multipart
        try:
            client.abort_multipart_upload(...)
        except Exception:
            pass
        session.status = 'expired'
        session.save()
```

---

## Common Pitfalls

### 1. Loading Whole File into Memory

```python
content = await file.read()   # 5GB → 5GB RAM
```

Use chunks:

```python
async with aiofiles.open(path, 'wb') as f:
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk: break
        await f.write(chunk)
```

### 2. nginx Default 1MB Limit

```
413 Request Entity Too Large
```

```nginx
client_max_body_size 50M;
```

### 3. Proxy Through App for Huge Files

50MB through Django/FastAPI = memory + slow. Use S3 presigned PUT.

### 4. No Cleanup for Incomplete Uploads

Multipart uploads → orphans in S3 → infinite storage cost. Lifecycle rule mandatory.

### 5. Trusting Client Content-Type

```python
if file.content_type == 'image/jpeg':   # client controls
```

Use libmagic on actual bytes.

### 6. Forgetting Virus Scan

Allowing upload of malicious files. Async ClamAV scan + mark pending → safe.

### 7. Same Path = Overwrite Risk

```python
path = f'uploads/{user.id}/{filename}'   # multiple uploads of "doc.pdf" overwrite
```

Use UUID prefix:

```python
path = f'uploads/{user.id}/{uuid4()}/{filename}'
```

---

## Interview Q&A

**Q1:** 500MB video upload — design?
**A:** S3 multipart upload with presigned URLs. Client splits into 5MB chunks, uploads in parallel directly to S3 (not proxied through backend). Backend: (1) init endpoint → S3 upload_id. (2) per-part URL endpoint. (3) complete endpoint → S3 finalize. Resumable: failed chunks retry individually. Save bandwidth + RAM on backend.

**Q2:** Resumable upload implementation?
**A:** Track session in DB with `received_bytes` + S3 `upload_id`. Client uploads chunks, server records each acknowledged part. On disconnect, client queries session → resumes from last successful chunk. tus protocol standardizes this.

**Q3:** Security checklist for uploads?
**A:** (1) Size limit (nginx + app + S3 condition). (2) MIME via libmagic (not header). (3) Extension whitelist. (4) Filename sanitize + UUID path. (5) Private S3 ACL. (6) Async virus scan (ClamAV). (7) Short presigned TTL. (8) Block executable extensions. (9) SSE-S3 encryption. (10) Per-tenant bucket isolation.

**Q4:** Direct-to-S3 vs proxy?
**A:** Direct: backend bandwidth saved, memory not consumed, faster (no extra hop). Cons: need presigned URL flow (2 round-trips). Proxy: simpler API, can do real-time validation, but expensive at scale. Direct preferred for >10MB.

**Q5:** Image bomb attack?
**A:** Small file (KB) that decodes to GBs of pixels → OOM. Prevention: `Image.MAX_IMAGE_PIXELS = 100_000_000`. Pre-check dimensions before full decode: `Image.open(...).size`. Use ImageMagick limits if processing. Reject files claiming huge dimensions.

**Q6:** Virus scanning strategy?
**A:** Async via Celery — don't block upload response. Set file `scan_status='pending'` initially; block read access until 'clean'. ClamAV (self-hosted) or AWS Lambda + ClamScan. On infection: quarantine bucket + alert. False positives — manual review queue.

**Q7:** Multipart upload failure recovery?
**A:** Client tracks completed parts. On failure: retry individual failed parts (not entire upload). S3 multipart auto-aborts incomplete after lifecycle period. Server endpoint to list session status: which parts succeeded.

**Q8:** Pre-signed URL vs POST policy?
**A:** PUT URL: single object, simple. POST policy: form-based, supports conditions (content-type whitelist, max size). POST better for browser uploads + policy enforcement. PUT for direct API uploads (mobile, SDK).

---

## Real-World Use Cases

### 1. Profile Avatar (Small Direct)

```python
@app.post('/avatar', dependencies=[Depends(rate_limit_5_per_min)])
async def upload_avatar(file: UploadFile = File(...), user=Depends(get_user)):
    validate_image(file, max_dimensions=(1024, 1024))

    # Resize before storing
    img = Image.open(file.file)
    img.thumbnail((512, 512))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)

    # Upload to S3
    key = f'avatars/{user.id}.jpg'
    s3.put_object(
        Bucket='my-bucket',
        Key=key,
        Body=buf.getvalue(),
        ContentType='image/jpeg',
        ACL='public-read',
    )

    user.avatar_url = f'https://cdn.example.com/{key}'
    user.save()
```

### 2. Video Upload (Multipart + Transcoding)

Init multipart → parallel chunk uploads → complete → trigger transcoding job (ffmpeg in Lambda or ECS) → multiple resolution outputs.

### 3. Bulk Document Import

Generate presigned POST URLs for batch. Frontend uploads each. After all complete, POST to /import endpoint with keys → start indexing job.

---

## References

- [S3 Multipart Upload](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
- [tus.io — resumable upload protocol](https://tus.io/)
- [Boto3 presigned URLs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html)
- [ClamAV](https://www.clamav.net/)
