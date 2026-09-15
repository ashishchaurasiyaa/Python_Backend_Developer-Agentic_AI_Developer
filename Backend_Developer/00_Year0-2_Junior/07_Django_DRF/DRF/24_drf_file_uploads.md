# DRF File Uploads — Multipart, Chunked, S3 Direct

## Why It Matters (Senior 5 YOE Context)

File upload in DRF has gotchas — wrong approach = OOM, slow uploads, security holes. Senior 5 YOE must know:

- **Small files** (<5 MB): multipart through Django (simple)
- **Medium files** (5-100 MB): streamed multipart with size limits
- **Large files** (>100 MB): S3 direct upload via presigned URL (don't proxy)
- **Chunked uploads**: Resume-from-failure for unreliable networks (mobile)
- **Security**: MIME validation, virus scan, content sniffing prevention

Interview ask: "Mobile app uploads 200 MB video. Design the API." → S3 multipart presigned + completion endpoint + virus scan async.

---

## Core Concepts

### Basic Multipart Upload via DRF

```python
from rest_framework import serializers, viewsets
from rest_framework.parsers import MultiPartParser, FormParser


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    queryset = Document.objects.all()
    parser_classes = [MultiPartParser, FormParser]   # required

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)
```

```bash
curl -F "title=Resume" -F "file=@resume.pdf" \
  -H "Authorization: Token xxx" \
  http://api.example.com/docs/
```

### Streaming Upload (Avoid Loading into Memory)

```python
# settings.py
FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
    # 'django.core.files.uploadhandler.MemoryFileUploadHandler',  # remove
]

FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024   # 2 MB threshold
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100
```

Now files >2 MB stream to temp disk instead of memory.

### Content Validation (MIME, Size, Extension)

```python
import magic
from rest_framework.exceptions import ValidationError


ALLOWED_MIMES = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'application/pdf': '.pdf',
}

MAX_SIZE = 50 * 1024 * 1024  # 50 MB


def validate_upload(uploaded_file):
    if uploaded_file.size > MAX_SIZE:
        raise ValidationError(f'File too large (max {MAX_SIZE // 1024 // 1024} MB)')

    # Read first 2KB for libmagic
    head = uploaded_file.read(2048)
    uploaded_file.seek(0)
    detected_mime = magic.from_buffer(head, mime=True)

    if detected_mime not in ALLOWED_MIMES:
        raise ValidationError(f'Unsupported type: {detected_mime}')

    # Cross-check Content-Type header
    if uploaded_file.content_type != detected_mime:
        raise ValidationError('Content-Type mismatch — possible smuggling')

    # Cross-check extension
    expected_ext = ALLOWED_MIMES[detected_mime]
    if not uploaded_file.name.lower().endswith(expected_ext):
        raise ValidationError('Extension mismatch')


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['file']

    def validate_file(self, value):
        validate_upload(value)
        return value
```

### Image-Specific (Pillow Validation)

```python
from PIL import Image


def validate_image(uploaded_file, max_dimensions=(4000, 4000)):
    try:
        img = Image.open(uploaded_file)
        img.verify()  # checks integrity (basic)
    except Exception:
        raise ValidationError('Invalid image')

    uploaded_file.seek(0)
    img = Image.open(uploaded_file)
    if img.width > max_dimensions[0] or img.height > max_dimensions[1]:
        raise ValidationError(f'Dimensions exceed {max_dimensions}')
    uploaded_file.seek(0)
```

### Filename Sanitization

```python
import os
import re
from uuid import uuid4


def safe_filename(original):
    """Strip path components and dangerous chars."""
    name = os.path.basename(original)
    # Remove control chars, only allow alnum + dash + underscore + dot
    name = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    return name


def upload_to_safe(instance, filename):
    safe = safe_filename(filename)
    return f'docs/{instance.user_id}/{uuid4()}-{safe}'
```

### S3 Presigned PUT Upload (Direct Browser → S3)

```python
import boto3
from botocore.config import Config


class UploadInitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        content_type = request.data.get('content_type')
        if content_type not in ALLOWED_MIMES:
            return Response({'error': 'Invalid type'}, status=400)

        key = f'uploads/{request.user.id}/{uuid4()}'
        client = boto3.client('s3', config=Config(signature_version='s3v4'))
        url = client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': key,
                'ContentType': content_type,
                'ContentLength': request.data.get('size'),  # exact size enforced
                'ServerSideEncryption': 'AES256',
            },
            ExpiresIn=300,
        )
        return Response({'upload_url': url, 'key': key})


class UploadCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        key = request.data.get('key')
        if not key.startswith(f'uploads/{request.user.id}/'):
            return Response({'error': 'Invalid key'}, status=400)

        # Verify file in S3
        client = boto3.client('s3')
        try:
            head = client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
        except client.exceptions.ClientError:
            return Response({'error': 'Upload not found'}, status=404)

        # Cross-check MIME post-upload (S3 stores Content-Type)
        if head['ContentType'] not in ALLOWED_MIMES:
            client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
            return Response({'error': 'Invalid type'}, status=400)

        # Save reference in DB
        doc = Document.objects.create(
            uploaded_by=request.user,
            s3_key=key,
            size=head['ContentLength'],
            content_type=head['ContentType'],
        )

        # Async virus scan
        from blog.tasks import virus_scan_document
        virus_scan_document.delay(doc.id)

        return Response(DocumentSerializer(doc).data)
```

### Chunked / Multipart S3 Upload (>100 MB)

For very large files (videos, datasets), use S3 multipart upload:

```python
class MultipartInitView(APIView):
    def post(self, request):
        key = f'uploads/{request.user.id}/{uuid4()}'
        client = boto3.client('s3')
        resp = client.create_multipart_upload(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=key,
            ContentType=request.data['content_type'],
            ServerSideEncryption='AES256',
        )
        return Response({
            'upload_id': resp['UploadId'],
            'key': key,
        })


class MultipartPartUrlView(APIView):
    def post(self, request):
        client = boto3.client('s3')
        url = client.generate_presigned_url(
            'upload_part',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': request.data['key'],
                'UploadId': request.data['upload_id'],
                'PartNumber': request.data['part_number'],
            },
            ExpiresIn=3600,
        )
        return Response({'url': url})


class MultipartCompleteView(APIView):
    def post(self, request):
        # parts = [{'ETag': '...', 'PartNumber': 1}, ...]
        client = boto3.client('s3')
        client.complete_multipart_upload(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=request.data['key'],
            UploadId=request.data['upload_id'],
            MultipartUpload={'Parts': request.data['parts']},
        )
        # Create DB record
        return Response({'status': 'completed'})
```

### Resumable Upload Pattern (Custom Implementation)

```python
# Track upload sessions in DB
class UploadSession(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    total_size = models.BigIntegerField()
    chunk_size = models.IntegerField(default=5 * 1024 * 1024)
    received_bytes = models.BigIntegerField(default=0)
    s3_upload_id = models.CharField(max_length=200)
    parts = models.JSONField(default=list)
    status = models.CharField(default='active')
    expires_at = models.DateTimeField()
```

Client uploads chunks with offset; server tracks; resume from last received byte.

---

## How It Works Internally

### Multipart Parser

```
POST /upload/ HTTP/1.1
Content-Type: multipart/form-data; boundary=----WebKitForm

------WebKitForm
Content-Disposition: form-data; name="title"

My Document
------WebKitForm
Content-Disposition: form-data; name="file"; filename="doc.pdf"
Content-Type: application/pdf

<binary>
------WebKitForm--
```

Django's `MultiPartParser` streams parts. Files > `FILE_UPLOAD_MAX_MEMORY_SIZE` written to disk; others in memory.

### S3 Presigned URL Signing

```python
# Signature includes:
# - bucket, key, content-type, content-length
# - expiry timestamp
# - HMAC-SHA256 with AWS secret key

# Frontend can't change any signed field without invalidating
```

### Multipart S3 Limits

- Part size: 5 MB minimum (except last), max 5 GB
- Max parts: 10,000
- Total: up to 5 TB
- Lifecycle: auto-abort incomplete after N days (configure!)

---

## Common Pitfalls

### 1. Loading Whole File into Memory

```python
# BAD
data = uploaded_file.read()  # 200 MB into RAM
```

**Fix:** Stream:

```python
for chunk in uploaded_file.chunks():
    # process chunk
```

### 2. Trusting Content-Type Header

Client can lie. Use libmagic on actual bytes.

### 3. Path Traversal via Filename

`filename="../../../etc/passwd"` — strip path components, use UUID.

### 4. Not Aborting Multipart Uploads

Incomplete S3 multipart uploads = silent storage cost. Bucket lifecycle:

```json
{"Rules": [{
  "ID": "abort-multipart",
  "Status": "Enabled",
  "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
}]}
```

### 5. Direct S3 Without CORS

Browser PUT to S3 blocked without CORS config on bucket.

### 6. Virus Scan Skipped

Always scan async (ClamAV via Lambda, or 3rd-party like S3 Antivirus). Mark file `pending_scan` initially, allow access only after clean.

### 7. Large File Timeout

Nginx `client_max_body_size 100M;` default 1 MB. Adjust if proxying uploads. Better: direct S3, avoid proxy.

### 8. Image Bombs (Decompression Bombs)

```python
# 1 KB PNG decompresses to 10 GB
Image.MAX_IMAGE_PIXELS = 100_000_000  # cap
```

---

## Interview Q&A

**Q1:** 200 MB file upload kaise design karoge?
**A:** S3 presigned PUT (single object up to 5 GB) — frontend uploads directly, backend just signs URL + creates DB record on completion. For >5 GB or unreliable network: multipart upload (chunks of 5 MB, resumable). Never proxy through Django server.

**Q2:** File type validation Django mein?
**A:** Three layers: (1) Extension check (cheap, bypass-able). (2) libmagic on actual bytes (reliable). (3) Cross-check Content-Type header matches detected MIME. Also size limit + extension whitelist. Reject on any mismatch.

**Q3:** Virus scan kaise integrate karoge?
**A:** Async via Celery. Set file `pending_scan` initially. Scanner task: ClamAV (self-hosted), or AWS Lambda + ClamScan, or 3rd-party (Sophos Cloud Scan API). On clean: mark `safe`, allow access. On infected: quarantine + alert.

**Q4:** Multipart S3 upload kab use karoge?
**A:** Files > 100 MB, or unreliable networks (mobile). Benefits: resumable (don't re-upload failed chunks), parallel chunks (faster), per-part retry. Trade-off: more API calls, more complex client. For < 100 MB single PUT is simpler.

**Q5:** Chunked resumable upload server-side kaise implement karoge?
**A:** Track UploadSession in DB with `received_bytes`, `parts` (S3 upload_id), `expires_at`. Client uploads with offset header. Server signs next part URL, updates received_bytes. On client failure, client queries session → resumes from last received.

**Q6:** File upload security checklist?
**A:** (1) Size limit (DRF + S3 condition). (2) Real MIME via libmagic. (3) Cross-check headers. (4) Sanitize filename. (5) UUID in path (no client-controlled paths). (6) SSE-S3/KMS encryption. (7) Private ACL. (8) Short presigned TTL. (9) Async virus scan. (10) CORS allowed-origins explicit.

**Q7:** Image decompression bomb kya hai?
**A:** Small file (KB) that expands to GBs of pixels when decoded → OOM crash. Mitigate with `Image.MAX_IMAGE_PIXELS = 100_000_000` (about 100 MP cap). Or pre-validate dimensions via `Image.open(...).size` before `.verify()`. ImageMagick `--max-memory` equivalents.

**Q8:** Browser → S3 direct upload mein backend ka role?
**A:** Sign URL (proves authorization without giving away AWS keys), enforce policy (content-type, max size via conditions), receive completion notification (create DB record, trigger downstream like virus scan). Backend sees no file bytes — bandwidth/memory not consumed.

---

## Real-World Use Cases

### 1. Profile Avatar (Small, Validated)

```python
class AvatarUploadView(APIView):
    def post(self, request):
        f = request.FILES['avatar']
        validate_image(f, max_dimensions=(1024, 1024))
        # resize to fit
        img = Image.open(f)
        img.thumbnail((512, 512))
        # save via storage
```

### 2. Document Repository (Mid-size, Direct S3)

Presigned PUT → DB record → virus scan → indexed for search.

### 3. Video Upload (Large, Multipart)

Initiate multipart → frontend uploads parts in parallel (5 MB each) → complete → trigger transcoding job → mark ready when done.

---

## References

- [DRF parsers](https://www.django-rest-framework.org/api-guide/parsers/)
- [Django file uploads](https://docs.djangoproject.com/en/5.0/topics/http/file-uploads/)
- [S3 multipart upload](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
- libmagic, python-magic
- ClamAV integration patterns
