# Django Storage Backends — S3, Presigned URLs, Direct Upload

## Why It Matters (Senior 5 YOE Context)

Default `FileSystemStorage` works for single-server dev. Production = **must** move uploads off the app server:

- **Scaling** → multiple app instances can't share local files
- **CDN** → static files served from CloudFront/Cloudflare
- **Cost** → S3 storage cheaper than EBS, lifecycle policies (Glacier)
- **Security** → presigned URLs for time-limited access
- **Performance** → direct browser → S3 upload (offloads app server)

Senior interview: "Users upload 50 MB PDFs. How do you avoid sending the file through Django?" → **presigned URL direct upload**.

---

## Core Concepts

### django-storages with S3

```python
# pip install django-storages[boto3]
# settings.py

INSTALLED_APPS += ['storages']

# Default storage = S3
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": "static.example.com",
            "querystring_auth": False,  # public static files
            "default_acl": "public-read",
        },
    },
}

# S3 config
AWS_STORAGE_BUCKET_NAME = 'media.example.com'
AWS_S3_REGION_NAME = 'us-east-1'
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_S3_FILE_OVERWRITE = False         # rename if collision
AWS_DEFAULT_ACL = 'private'           # private by default
AWS_QUERYSTRING_EXPIRE = 3600          # presigned URL TTL
AWS_S3_CUSTOM_DOMAIN = 'cdn.example.com'

# IAM credentials — use IAM role on EC2/ECS, not keys
# AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
# AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
```

### FileField + S3

```python
from django.db import models


class UserDocument(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    file = models.FileField(upload_to='docs/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


# Usage
doc = UserDocument.objects.create(user=user, file=request.FILES['file'])
print(doc.file.url)   # https://media.example.com/docs/2026/01/abc.pdf?Signature=...&Expires=...
```

### Presigned URLs (Backend Generates, Frontend Uploads)

```python
import boto3
from botocore.config import Config
from django.conf import settings


def get_s3_client():
    return boto3.client(
        's3',
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(signature_version='s3v4'),
    )


def generate_presigned_upload_url(key, content_type, expires_in=300):
    """Generate URL frontend can PUT directly to."""
    client = get_s3_client()
    url = client.generate_presigned_url(
        ClientMethod='put_object',
        Params={
            'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
            'Key': key,
            'ContentType': content_type,
            'ServerSideEncryption': 'AES256',
        },
        ExpiresIn=expires_in,
    )
    return url
```

### Presigned POST (Browser Form Upload with Conditions)

```python
def generate_presigned_post(key, content_type, max_size=10 * 1024 * 1024):
    client = get_s3_client()
    return client.generate_presigned_post(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=key,
        Fields={
            'Content-Type': content_type,
            'x-amz-server-side-encryption': 'AES256',
        },
        Conditions=[
            {'Content-Type': content_type},
            ['content-length-range', 1, max_size],
            {'x-amz-server-side-encryption': 'AES256'},
        ],
        ExpiresIn=300,
    )
    # Returns: {'url': '...', 'fields': {'key': ..., 'policy': ..., ...}}
```

### Frontend Upload Flow

```javascript
// 1. Get presigned URL from backend
const { url, fields } = await fetch('/api/upload-url/').then(r => r.json());

// 2. Direct browser → S3
const form = new FormData();
for (const [k, v] of Object.entries(fields)) form.append(k, v);
form.append('file', fileInput.files[0]);

await fetch(url, { method: 'POST', body: form });

// 3. Notify backend of completion
await fetch('/api/upload-complete/', {
  method: 'POST',
  body: JSON.stringify({ key: fields.key }),
});
```

### Custom Storage Backend

```python
from storages.backends.s3 import S3Storage


class PublicMediaStorage(S3Storage):
    location = 'public'
    default_acl = 'public-read'
    file_overwrite = False
    querystring_auth = False  # no signed URLs


class PrivateMediaStorage(S3Storage):
    location = 'private'
    default_acl = 'private'
    file_overwrite = False
    custom_domain = None  # force signed URLs via S3 endpoint
    querystring_auth = True
    querystring_expire = 3600


# Use per-model
class Avatar(models.Model):
    image = models.ImageField(storage=PublicMediaStorage())


class TaxDocument(models.Model):
    file = models.FileField(storage=PrivateMediaStorage())
```

### Signed Cookie for Bulk Access

For protected video streaming / many files: CloudFront signed cookies.

```python
from botocore.signers import CloudFrontSigner
# Returns set-cookie headers that allow access to anything under a path
```

---

## How It Works Internally

### `FileField.url` Resolution

```python
# 1. file.name = 'docs/2026/01/abc.pdf'  (stored in DB)
# 2. storage._open(name) when read
# 3. file.url:
#    - FileSystemStorage: MEDIA_URL + name
#    - S3Storage: presigned URL (if querystring_auth) or public URL
```

### `save()` and Overwrite Behavior

```python
# Default S3Storage:
AWS_S3_FILE_OVERWRITE = False  # appends _<random> on collision

# Storage.save(name, content) internally:
# - Calls get_available_name(name) → unique filename
# - Calls _save(name, content) → actual upload
```

### Server-Side Encryption (SSE)

```python
AWS_S3_OBJECT_PARAMETERS = {
    'ServerSideEncryption': 'AES256',  # SSE-S3
    # Or: 'aws:kms' + 'SSEKMSKeyId': 'arn:aws:kms:...'
}
```

---

## Common Pitfalls

### 1. Public Bucket by Accident

```python
AWS_DEFAULT_ACL = 'public-read'  # entire bucket public!
```

**Fix:** `AWS_DEFAULT_ACL = 'private'`, use per-storage `public_read` only for static.

### 2. Hardcoded Credentials

Use IAM roles on EC2/ECS/Lambda. Never `AWS_ACCESS_KEY_ID` in settings file.

### 3. Slow `file.url` Calls

`querystring_auth = True` triggers a new presigned URL signing per access:

```python
# Pitfall — signed URL per article in list
for a in Article.objects.all():
    a.thumbnail.url  # signing each time
```

**Fix:** Cache URL or use CloudFront with `querystring_auth = False`.

### 4. Browser Cache + Overwrite

If you overwrite the same key, browsers cache the old version. Solution: include hash/version in path:

```python
def upload_to(instance, filename):
    import uuid
    return f'docs/{uuid.uuid4()}/{filename}'
```

### 5. Presigned URL TTL Too Long

`querystring_expire = 86400` (1 day) = link can be shared. Use 5-15 min for sensitive content.

### 6. CORS Not Configured on S3

Browser upload via presigned POST blocked by CORS. Configure bucket:

```json
[
  {
    "AllowedOrigins": ["https://app.example.com"],
    "AllowedMethods": ["PUT", "POST", "GET"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3000
  }
]
```

### 7. Multipart Uploads Not Auto-Cleaned

S3 incomplete multipart uploads = silent billing. Lifecycle rule:

```json
{
  "Rules": [{
    "ID": "abort-incomplete-multipart",
    "Status": "Enabled",
    "AbortIncompleteMultipartUpload": { "DaysAfterInitiation": 7 }
  }]
}
```

### 8. Cost of `file.size`

`FileField.size` calls `HEAD` on S3 (network call) for each access. Store size in DB column at upload time.

---

## Interview Q&A

**Q1:** 50 MB file upload Django se kaise efficiently handle karoge?
**A:** Don't proxy through Django. Two patterns: (1) **Presigned PUT** — backend generates URL, frontend PUTs directly to S3. (2) **Presigned POST** — backend signs a policy, frontend submits form fields + file to S3. After upload, frontend notifies backend to create DB record. Saves bandwidth + memory + time.

**Q2:** Private vs public S3 files Django mein kaise handle karte ho?
**A:** Two storage classes. Public (avatars, thumbnails) → `default_acl = 'public-read'`, `querystring_auth = False`, served via CloudFront. Private (tax docs) → `default_acl = 'private'`, `querystring_auth = True`, generates signed URL per access (short TTL).

**Q3:** S3 keys ko collision-safe kaise banaoge?
**A:** `AWS_S3_FILE_OVERWRITE = False` → django-storages appends random suffix. Better: use `upload_to` with UUID prefix: `f'docs/{uuid4()}/{filename}'`. Best: hash-based path for content-addressable storage.

**Q4:** Presigned URL TTL kya hona chahiye?
**A:** Trade-off: shorter = more secure, more re-requests; longer = less requests, more leak risk. Sensitive content: 5-15 min. Avatar/public: 1 hour. Static via CloudFront: signed cookie for session-long access.

**Q5:** CDN ke saath signed URL kaise integrate karoge?
**A:** CloudFront signed URLs/cookies (via private key). Or S3-direct signed URLs cached at CDN with `Vary: <signature>`. Pattern: CloudFront for public + caching, S3-direct presigned for private downloads.

**Q6:** File upload security checklist?
**A:** (1) Validate MIME via libmagic (not just extension), (2) Size limit (S3 condition + Django setting), (3) Filename sanitization (no `../` traversal), (4) Virus scan async via Lambda/ClamAV, (5) Private by default, (6) Short TTL on URLs, (7) SSE-S3 or KMS encryption, (8) Audit log of access.

**Q7:** Multiple app instances kaise share kar sakte files (no S3)?
**A:** NFS / EFS for shared filesystem (works but slow, single point of failure). Better: S3 + CloudFront. Or self-host MinIO (S3-compatible) on-prem.

**Q8:** Old uploads ko delete kaise karoge — Django model delete pe?
**A:** Django doesn't auto-delete S3 file on model delete. Use signal:
```python
@receiver(post_delete, sender=UserDocument)
def delete_s3_file(sender, instance, **kwargs):
    instance.file.delete(save=False)
```
Risk: orphaned files if signal fails. Better: scheduled cleanup task comparing DB ↔ S3.

---

## Real-World Use Cases

### 1. User Avatar Upload (small, public)

```python
class Avatar(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    image = models.ImageField(
        storage=PublicMediaStorage(),
        upload_to='avatars/',
    )
```

### 2. Tax Document (large, private)

```python
class TaxDocument(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    file = models.FileField(storage=PrivateMediaStorage(), upload_to='tax/')
    year = models.IntegerField()


# View
def download_tax(request, doc_id):
    doc = get_object_or_404(TaxDocument, id=doc_id, user=request.user)
    return JsonResponse({'url': doc.file.url})  # short-lived signed
```

### 3. Direct Browser Upload (large videos)

```python
def get_upload_url(request):
    key = f'videos/{request.user.id}/{uuid4()}/{request.GET["filename"]}'
    return JsonResponse(generate_presigned_post(key, 'video/mp4', max_size=500*1024*1024))


def upload_complete(request):
    key = request.POST['key']
    # Verify file exists in S3
    s3 = get_s3_client()
    head = s3.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
    Video.objects.create(user=request.user, s3_key=key, size=head['ContentLength'])
    return JsonResponse({'ok': True})
```

---

## References

- [django-storages docs](https://django-storages.readthedocs.io/)
- [boto3 S3 presigned URLs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html)
- [S3 best practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
- AWS blog: "Direct upload from browser to S3"
