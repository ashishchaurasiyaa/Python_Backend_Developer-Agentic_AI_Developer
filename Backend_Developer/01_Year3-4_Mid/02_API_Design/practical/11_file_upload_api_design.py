"""
File Upload API — Production Patterns
"""

import os
import re
import uuid
import asyncio
import io
from datetime import datetime, timedelta

import boto3
from botocore.config import Config
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


app = FastAPI()


# ==========================================================================
# 1. S3 CLIENT
# ==========================================================================

s3_client = boto3.client(
    's3',
    region_name=os.environ.get('AWS_REGION', 'us-east-1'),
    config=Config(signature_version='s3v4'),
)


BUCKET = os.environ.get('S3_BUCKET', 'my-bucket')


# ==========================================================================
# 2. VALIDATION HELPERS
# ==========================================================================

ALLOWED_MIMES = {
    'image/jpeg': {'.jpg', '.jpeg'},
    'image/png': {'.png'},
    'image/webp': {'.webp'},
    'application/pdf': {'.pdf'},
    'video/mp4': {'.mp4'},
    'application/msword': {'.doc'},
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {'.docx'},
}


MAX_SIZE_BY_TYPE = {
    'image/jpeg': 10 * 1024 * 1024,
    'image/png': 10 * 1024 * 1024,
    'image/webp': 10 * 1024 * 1024,
    'application/pdf': 50 * 1024 * 1024,
    'video/mp4': 5 * 1024 * 1024 * 1024,  # 5GB
    'application/msword': 50 * 1024 * 1024,
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 50 * 1024 * 1024,
}


DENIED_EXTENSIONS = {'.exe', '.bat', '.cmd', '.sh', '.ps1', '.app', '.dmg', '.scr'}


def sanitize_filename(filename: str) -> str:
    """Strip path + dangerous chars."""
    name = os.path.basename(filename)
    name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    return name[:200]


def safe_s3_key(user_id: int, filename: str) -> str:
    """UUID-prefixed — no client-controlled paths."""
    safe = sanitize_filename(filename)
    ext = os.path.splitext(safe)[1].lower()
    if ext in DENIED_EXTENSIONS:
        raise HTTPException(415, f'Extension {ext} not allowed')
    return f'uploads/{user_id}/{uuid.uuid4()}/{safe}'


def validate_upload(file: UploadFile, expected_type: str = None):
    """Cross-validate MIME via libmagic."""

    # Size pre-check (best effort — UploadFile.size may be None)
    if file.size and file.size > MAX_SIZE_BY_TYPE.get(file.content_type, 50 * 1024 * 1024):
        raise HTTPException(413, 'File too large')

    # MIME via libmagic
    try:
        import magic
        head = file.file.read(2048)
        file.file.seek(0)
        detected = magic.from_buffer(head, mime=True)
    except ImportError:
        detected = file.content_type

    if detected not in ALLOWED_MIMES:
        raise HTTPException(415, f'Unsupported type: {detected}')

    if expected_type and detected != expected_type:
        raise HTTPException(400, f'Type mismatch: expected {expected_type}, got {detected}')

    # Extension check
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext and ext not in ALLOWED_MIMES[detected]:
        raise HTTPException(400, f'Extension/content mismatch: {ext} vs {detected}')

    return detected


def validate_image(file_obj, max_dimensions=(4000, 4000)):
    """Image-specific validation — prevent decompression bombs."""
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = 100_000_000   # 100MP cap

    try:
        img = Image.open(file_obj)
        img.verify()
    except Exception as e:
        raise HTTPException(400, f'Invalid image: {e}')

    file_obj.seek(0)
    img = Image.open(file_obj)
    if img.width > max_dimensions[0] or img.height > max_dimensions[1]:
        raise HTTPException(400, f'Dimensions {img.width}x{img.height} too large')
    file_obj.seek(0)


# ==========================================================================
# 3. SIMPLE DIRECT UPLOAD (< 10MB)
# ==========================================================================

@app.post('/uploads/direct')
async def direct_upload(
    file: UploadFile = File(...),
    user_id: int = 1,   # from auth
):
    """Stream to S3 in chunks — never load whole file in memory."""
    detected_mime = validate_upload(file)

    key = safe_s3_key(user_id, file.filename)

    # Stream upload to S3
    try:
        s3_client.upload_fileobj(
            file.file,
            BUCKET,
            key,
            ExtraArgs={
                'ContentType': detected_mime,
                'ServerSideEncryption': 'AES256',
                'ACL': 'private',
                'Metadata': {
                    'uploaded_by': str(user_id),
                    'original_filename': sanitize_filename(file.filename),
                },
            },
        )
    except Exception as e:
        raise HTTPException(500, f'Upload failed: {e}')

    # Create DB record (mock)
    document_id = uuid.uuid4().hex

    # Async virus scan
    # scan_for_viruses.delay(document_id)

    return {
        'id': document_id,
        'key': key,
        'size': file.size,
        'content_type': detected_mime,
        'scan_status': 'pending',
    }


# ==========================================================================
# 4. PRESIGNED PUT (single object, < 5GB)
# ==========================================================================

class PresignedUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_type: str
    size: int = Field(gt=0)


@app.post('/uploads/presigned/init')
async def init_presigned_upload(payload: PresignedUploadRequest, user_id: int = 1):
    # Validate type
    if payload.content_type not in ALLOWED_MIMES:
        raise HTTPException(415, 'Invalid content type')

    # Validate size
    max_size = MAX_SIZE_BY_TYPE.get(payload.content_type, 50 * 1024 * 1024)
    if payload.size > max_size:
        raise HTTPException(413, f'Max {max_size // 1024 // 1024} MB')

    # Validate extension
    ext = os.path.splitext(payload.filename)[1].lower()
    if ext in DENIED_EXTENSIONS:
        raise HTTPException(415, f'Extension {ext} blocked')

    key = safe_s3_key(user_id, payload.filename)

    url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': BUCKET,
            'Key': key,
            'ContentType': payload.content_type,
            'ContentLength': payload.size,
            'ServerSideEncryption': 'AES256',
        },
        ExpiresIn=300,    # 5 min
    )

    return {
        'upload_url': url,
        'method': 'PUT',
        'key': key,
        'headers': {
            'Content-Type': payload.content_type,
            'x-amz-server-side-encryption': 'AES256',
        },
        'expires_in': 300,
    }


@app.post('/uploads/presigned/complete')
async def complete_presigned(key: str, user_id: int = 1):
    """Verify upload succeeded, create DB record."""

    # Validate key belongs to user
    prefix = f'uploads/{user_id}/'
    if not key.startswith(prefix):
        raise HTTPException(400, 'Invalid key')

    # Verify in S3
    try:
        head = s3_client.head_object(Bucket=BUCKET, Key=key)
    except s3_client.exceptions.ClientError:
        raise HTTPException(404, 'Upload not found in S3')

    # Verify type post-upload
    if head['ContentType'] not in ALLOWED_MIMES:
        s3_client.delete_object(Bucket=BUCKET, Key=key)
        raise HTTPException(400, 'Invalid content type')

    max_size = MAX_SIZE_BY_TYPE.get(head['ContentType'], 50 * 1024 * 1024)
    if head['ContentLength'] > max_size:
        s3_client.delete_object(Bucket=BUCKET, Key=key)
        raise HTTPException(413, 'Too large')

    # Create DB record
    doc_id = uuid.uuid4().hex

    # Async virus scan
    # scan_for_viruses.delay(doc_id)

    return {
        'id': doc_id,
        'key': key,
        'size': head['ContentLength'],
        'content_type': head['ContentType'],
        'scan_status': 'pending',
    }


# ==========================================================================
# 5. S3 MULTIPART UPLOAD (> 100MB, resumable)
# ==========================================================================

# Mock session store (use DB in prod)
upload_sessions: dict[str, dict] = {}


class MultipartInitRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_type: str
    total_size: int = Field(gt=0)


@app.post('/uploads/multipart/init')
async def multipart_init(payload: MultipartInitRequest, user_id: int = 1):
    if payload.content_type not in ALLOWED_MIMES:
        raise HTTPException(415, 'Invalid type')

    max_size = MAX_SIZE_BY_TYPE.get(payload.content_type, 5 * 1024 * 1024 * 1024)
    if payload.total_size > max_size:
        raise HTTPException(413, 'Too large')

    key = safe_s3_key(user_id, payload.filename)

    # Initiate S3 multipart
    resp = s3_client.create_multipart_upload(
        Bucket=BUCKET,
        Key=key,
        ContentType=payload.content_type,
        ServerSideEncryption='AES256',
    )

    session_id = uuid.uuid4().hex
    upload_sessions[session_id] = {
        'user_id': user_id,
        'key': key,
        'upload_id': resp['UploadId'],
        'total_size': payload.total_size,
        'content_type': payload.content_type,
        'parts': [],
        'status': 'active',
        'expires_at': datetime.utcnow() + timedelta(hours=24),
    }

    chunk_size = 5 * 1024 * 1024   # 5MB minimum for S3 multipart
    num_parts = (payload.total_size + chunk_size - 1) // chunk_size

    return {
        'session_id': session_id,
        'chunk_size': chunk_size,
        'num_parts': num_parts,
        'expires_in': 86400,
    }


@app.post('/uploads/multipart/{session_id}/part/{part_number}/url')
async def get_part_url(session_id: str, part_number: int, user_id: int = 1):
    """Get presigned URL for one part."""
    session = upload_sessions.get(session_id)
    if not session or session['user_id'] != user_id:
        raise HTTPException(404, 'Session not found')

    if not 1 <= part_number <= 10000:
        raise HTTPException(400, 'Part number 1-10000')

    url = s3_client.generate_presigned_url(
        'upload_part',
        Params={
            'Bucket': BUCKET,
            'Key': session['key'],
            'UploadId': session['upload_id'],
            'PartNumber': part_number,
        },
        ExpiresIn=3600,
    )

    return {
        'url': url,
        'method': 'PUT',
        'part_number': part_number,
    }


class CompletePart(BaseModel):
    ETag: str
    PartNumber: int


class MultipartCompleteRequest(BaseModel):
    parts: list[CompletePart] = Field(min_length=1)


@app.post('/uploads/multipart/{session_id}/complete')
async def multipart_complete(session_id: str, payload: MultipartCompleteRequest, user_id: int = 1):
    session = upload_sessions.get(session_id)
    if not session or session['user_id'] != user_id:
        raise HTTPException(404)

    parts_sorted = sorted([p.model_dump() for p in payload.parts], key=lambda p: p['PartNumber'])

    try:
        s3_client.complete_multipart_upload(
            Bucket=BUCKET,
            Key=session['key'],
            UploadId=session['upload_id'],
            MultipartUpload={'Parts': parts_sorted},
        )
    except s3_client.exceptions.ClientError as e:
        raise HTTPException(400, f'Complete failed: {e}')

    session['status'] = 'completed'

    # Create DB record
    doc_id = uuid.uuid4().hex
    # scan_for_viruses.delay(doc_id)

    return {
        'id': doc_id,
        'key': session['key'],
        'size': session['total_size'],
    }


@app.post('/uploads/multipart/{session_id}/abort')
async def multipart_abort(session_id: str, user_id: int = 1):
    session = upload_sessions.get(session_id)
    if not session or session['user_id'] != user_id:
        raise HTTPException(404)

    try:
        s3_client.abort_multipart_upload(
            Bucket=BUCKET,
            Key=session['key'],
            UploadId=session['upload_id'],
        )
    except Exception:
        pass

    session['status'] = 'aborted'
    return {'aborted': True}


@app.get('/uploads/multipart/{session_id}/status')
async def multipart_status(session_id: str, user_id: int = 1):
    """Check which parts already uploaded (for resume)."""
    session = upload_sessions.get(session_id)
    if not session or session['user_id'] != user_id:
        raise HTTPException(404)

    # List parts already uploaded
    response = s3_client.list_parts(
        Bucket=BUCKET,
        Key=session['key'],
        UploadId=session['upload_id'],
    )

    parts = [
        {'PartNumber': p['PartNumber'], 'ETag': p['ETag'], 'Size': p['Size']}
        for p in response.get('Parts', [])
    ]

    return {
        'session_id': session_id,
        'status': session['status'],
        'parts_uploaded': len(parts),
        'parts': parts,
        'bytes_uploaded': sum(p['Size'] for p in parts),
        'total_size': session['total_size'],
    }


# ==========================================================================
# 6. CLEANUP — ORPHAN UPLOAD SESSIONS
# ==========================================================================

# @shared_task
async def cleanup_expired_sessions():
    """Periodic cleanup of expired sessions."""
    now = datetime.utcnow()

    expired = [
        (sid, session) for sid, session in upload_sessions.items()
        if session['expires_at'] < now and session['status'] == 'active'
    ]

    for session_id, session in expired:
        try:
            s3_client.abort_multipart_upload(
                Bucket=BUCKET,
                Key=session['key'],
                UploadId=session['upload_id'],
            )
        except Exception:
            pass
        session['status'] = 'expired'


# ==========================================================================
# 7. VIRUS SCAN (async via Celery)
# ==========================================================================

"""
import tempfile
import subprocess
from celery import shared_task


@shared_task
def virus_scan(doc_id):
    doc = Document.objects.get(pk=doc_id)
    doc.scan_status = 'scanning'
    doc.save(update_fields=['scan_status'])

    # Download from S3 to tmp
    with tempfile.NamedTemporaryFile() as tmp:
        s3_client.download_fileobj(BUCKET, doc.s3_key, tmp)
        tmp.flush()

        # ClamAV scan
        result = subprocess.run(
            ['clamdscan', '--no-summary', tmp.name],
            capture_output=True,
            timeout=300,
        )

    if result.returncode == 0:
        doc.scan_status = 'clean'
    elif result.returncode == 1:
        doc.scan_status = 'infected'
        # Quarantine
        s3_client.copy_object(
            Bucket='quarantine-bucket',
            Key=doc.s3_key,
            CopySource={'Bucket': BUCKET, 'Key': doc.s3_key},
        )
        s3_client.delete_object(Bucket=BUCKET, Key=doc.s3_key)
        notify_security_team(doc)
    else:
        doc.scan_status = 'failed'

    doc.save(update_fields=['scan_status'])
"""


# ==========================================================================
# 8. DOWNLOAD ENDPOINT (signed URL for access control)
# ==========================================================================

@app.get('/documents/{doc_id}/download')
async def download_url(doc_id: str, user_id: int = 1):
    # Lookup doc + check ownership
    # doc = Document.objects.get(pk=doc_id, user_id=user_id)
    # if doc.scan_status != 'clean':
    #     raise HTTPException(403, 'File not yet verified')

    # Generate short-lived signed URL
    url = s3_client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': BUCKET,
            'Key': 'mock/key',
            'ResponseContentDisposition': f'attachment; filename="doc.pdf"',
        },
        ExpiresIn=600,
    )
    return {'download_url': url, 'expires_in': 600}


# ==========================================================================
# 9. CORS CONFIG for S3 (browser direct upload)
# ==========================================================================

S3_CORS_CONFIG = """
# S3 bucket CORS — required for browser direct upload

[
    {
        "AllowedOrigins": ["https://app.example.com"],
        "AllowedMethods": ["GET", "PUT", "POST", "HEAD"],
        "AllowedHeaders": ["*"],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3000
    }
]
"""


# ==========================================================================
# 10. S3 LIFECYCLE (cleanup orphan multiparts)
# ==========================================================================

S3_LIFECYCLE_CONFIG = """
{
    "Rules": [
        {
            "ID": "abort-incomplete-multipart",
            "Status": "Enabled",
            "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
        },
        {
            "ID": "delete-old-uploads",
            "Status": "Enabled",
            "Filter": {"Prefix": "uploads/"},
            "Transitions": [
                {"Days": 30, "StorageClass": "STANDARD_IA"},
                {"Days": 90, "StorageClass": "GLACIER"}
            ]
        }
    ]
}
"""


# ==========================================================================
# 11. CLIENT-SIDE (JavaScript example)
# ==========================================================================

JS_CLIENT_EXAMPLE = """
// Browser client for multipart upload with resume

async function uploadFile(file) {
    // Init
    const initResp = await fetch('/uploads/multipart/init', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            filename: file.name,
            content_type: file.type,
            total_size: file.size,
        }),
    });
    const {session_id, chunk_size, num_parts} = await initResp.json();

    // Upload parts (with parallelism)
    const parts = [];
    const concurrent = 3;
    let next_part = 1;

    async function uploadNextPart() {
        while (next_part <= num_parts) {
            const part_num = next_part++;
            const start = (part_num - 1) * chunk_size;
            const end = Math.min(start + chunk_size, file.size);
            const chunk = file.slice(start, end);

            // Get presigned URL
            const urlResp = await fetch(`/uploads/multipart/${session_id}/part/${part_num}/url`, {
                method: 'POST',
            });
            const {url} = await urlResp.json();

            // PUT directly to S3 with retries
            let attempts = 0;
            while (attempts < 3) {
                try {
                    const putResp = await fetch(url, {method: 'PUT', body: chunk});
                    const etag = putResp.headers.get('etag').replace(/"/g, '');
                    parts.push({PartNumber: part_num, ETag: etag});
                    break;
                } catch (e) {
                    attempts++;
                    await new Promise(r => setTimeout(r, 1000 * attempts));
                }
            }
        }
    }

    await Promise.all([...Array(concurrent)].map(uploadNextPart));

    // Complete
    const completeResp = await fetch(`/uploads/multipart/${session_id}/complete`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({parts: parts.sort((a, b) => a.PartNumber - b.PartNumber)}),
    });
    return await completeResp.json();
}


// Resume after network failure
async function resumeUpload(session_id, file) {
    const statusResp = await fetch(`/uploads/multipart/${session_id}/status`);
    const {parts_uploaded, parts} = await statusResp.json();

    console.log(`Already uploaded ${parts_uploaded} parts, resuming...`);
    // Continue uploading remaining parts
}
"""
