# 02 — S3 & Presigned URLs

> The pattern for uploading and serving files at scale without your server being the bottleneck.

---

## Why Presigned URLs

Without:
```
Client → API → S3 → API → Client (for downloads)
Client → API → S3            (for uploads)
```

Your API server is in the path of every file transfer. Bandwidth, latency, cost — all bad.

With presigned URLs:
```
Client → API → "Here's a URL valid for 1 hour"
Client → S3 directly (upload or download)
```

API bandwidth: just the URL itself (~200 bytes). S3 handles GB transfers.

---

## How Presigned URLs Work

A signed URL contains:
- Bucket + key.
- HTTP method (GET, PUT, etc.).
- Expiry timestamp.
- HMAC signature using your AWS secret key.

```
https://my-bucket.s3.amazonaws.com/path/file.jpg
  ?X-Amz-Algorithm=AWS4-HMAC-SHA256
  &X-Amz-Credential=AKIA.../20240101/us-east-1/s3/aws4_request
  &X-Amz-Date=20240101T120000Z
  &X-Amz-Expires=3600
  &X-Amz-SignedHeaders=host
  &X-Amz-Signature=...
```

S3 verifies signature → if valid + not expired, allows action.

URL can be shared with anyone; only valid for the signed action + expiry.

---

## Generate Presigned GET URL (Download)

```python
import boto3
from botocore.config import Config

s3 = boto3.client(
    "s3",
    region_name="us-east-1",
    config=Config(signature_version="s3v4")
)

def get_download_url(bucket, key, expires_in=3600):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in
    )

url = get_download_url("my-bucket", "documents/file.pdf")
# Client downloads from this URL directly
```

### With response headers
Force download with custom filename:
```python
url = s3.generate_presigned_url(
    "get_object",
    Params={
        "Bucket": bucket,
        "Key": key,
        "ResponseContentDisposition": 'attachment; filename="report.pdf"'
    },
    ExpiresIn=3600
)
```

---

## Generate Presigned PUT URL (Upload)

```python
def get_upload_url(bucket, key, content_type, expires_in=3600):
    return s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket,
            "Key": key,
            "ContentType": content_type
        },
        ExpiresIn=expires_in
    )

# API endpoint
@app.post("/upload/init")
async def init_upload(req: InitRequest, user: User = Depends(get_user)):
    key = f"users/{user.id}/{uuid4()}-{req.filename}"
    url = get_upload_url("my-bucket", key, req.content_type)
    return {
        "upload_url": url,
        "key": key,
        "expires_in": 3600
    }
```

Client receives URL, uploads via PUT:
```javascript
fetch(upload_url, {
    method: "PUT",
    headers: {"Content-Type": file.type},
    body: file
});
```

After upload, client notifies your server (so you can record metadata):
```javascript
await fetch("/upload/complete", {
    method: "POST",
    body: JSON.stringify({ key, filename, size: file.size })
});
```

---

## Presigned POST (More Restrictive)

Lets you enforce conditions:
- Max size.
- Content-type prefix (`image/*`).
- Key prefix.

```python
post_data = s3.generate_presigned_post(
    Bucket="my-bucket",
    Key="users/${filename}",
    Fields={"Content-Type": "image/jpeg"},
    Conditions=[
        ["content-length-range", 0, 5 * 1024 * 1024],  # max 5MB
        ["starts-with", "$Content-Type", "image/"],
        {"Content-Type": "image/jpeg"}
    ],
    ExpiresIn=600
)

return post_data
# Returns: {"url": "...", "fields": {"key": "...", "AWSAccessKeyId": "...", "policy": "...", "signature": "..."}}
```

Client uploads as multipart form:
```javascript
const formData = new FormData();
Object.entries(post_data.fields).forEach(([k, v]) => formData.append(k, v));
formData.append("file", file);

await fetch(post_data.url, { method: "POST", body: formData });
```

Server enforces conditions; rejects oversized or wrong-type uploads.

---

## Direct Multipart Upload (Large Files > 5GB)

S3 multipart: split file into parts, upload in parallel, complete with manifest.

```python
# 1. Initiate
response = s3.create_multipart_upload(Bucket="my-bucket", Key="big-file.mp4")
upload_id = response["UploadId"]

# 2. Per-part presigned URLs
def get_part_url(part_number):
    return s3.generate_presigned_url(
        "upload_part",
        Params={
            "Bucket": "my-bucket",
            "Key": "big-file.mp4",
            "UploadId": upload_id,
            "PartNumber": part_number
        },
        ExpiresIn=3600
    )

# Client uploads parts in parallel; collects ETags
parts = [
    {"PartNumber": 1, "ETag": "..."},
    {"PartNumber": 2, "ETag": "..."},
    ...
]

# 3. Complete
s3.complete_multipart_upload(
    Bucket="my-bucket",
    Key="big-file.mp4",
    UploadId=upload_id,
    MultipartUpload={"Parts": parts}
)
```

### Cleanup orphan multiparts
Failed uploads leave partial data + you pay for it. Lifecycle rule:
```json
{
  "Rules": [{
    "Status": "Enabled",
    "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
  }]
}
```

---

## Security Considerations

### 1. Limit URL TTL
- Downloads: 15 min - 1 hour.
- Uploads: 15 min - 1 hour.
- Never use 7-day max default.

### 2. Restrict by IP (if possible)
```python
url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": bucket, "Key": key},
    ExpiresIn=3600,
    HttpMethod="GET"
)
```

Add `IPAddress` condition via signed policies for tighter control.

### 3. Don't expose AWS credentials
Generate URLs server-side; never give clients AWS keys.

### 4. Validate Content-Type at S3
Use presigned POST conditions to restrict file types.

### 5. Bucket policy as defense in depth
```json
{
  "Effect": "Deny",
  "Action": "s3:PutObject",
  "Resource": "arn:aws:s3:::my-bucket/*",
  "Condition": {
    "StringNotLike": {"s3:RequestObjectTagKeys": ["safe"]}
  }
}
```

### 6. Block public access
Disable public ACLs at bucket level. Only allow access via presigned URLs.

---

## S3 Best Practices

### Bucket structure
```
my-bucket/
  users/
    123/
      avatar.jpg
      docs/file.pdf
  shared/
    public-assets/
```

Use path prefixes for organization + access control.

### Naming convention
- Lowercase.
- Use hyphens, not underscores or spaces.
- Avoid sequential prefixes (S3 partitions by prefix; sequential = hot partition).

For high-throughput uploads, randomize prefix:
```
my-bucket/<uuid-prefix>/<actual-path>
```

### Encryption at rest
```python
s3.put_object(
    Bucket=bucket,
    Key=key,
    Body=data,
    ServerSideEncryption="AES256"   # or "aws:kms"
)
```

Default encryption: enable at bucket level.

### Lifecycle rules
Move to cheaper storage classes over time:
```json
{
  "Rules": [{
    "Filter": {"Prefix": "logs/"},
    "Transitions": [
      {"Days": 30, "StorageClass": "STANDARD_IA"},
      {"Days": 90, "StorageClass": "GLACIER"}
    ],
    "Expiration": {"Days": 365}
  }]
}
```

---

## CloudFront / CDN in Front of S3

For public assets (images, downloads):

```
Browser → CloudFront edge → cached?
                              yes → return
                              no → fetch from S3 → cache → return
```

Benefits:
- Lower latency (edge near user).
- Reduced S3 bandwidth bill (CloudFront cheaper).
- HTTPS termination.
- DDoS protection.
- Custom domain.

### CloudFront signed URLs
Same concept as S3 presigned, but signed by CloudFront:

```python
import datetime
from botocore.signers import CloudFrontSigner

def cloudfront_signed_url(url, expires_in=3600):
    expire_date = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
    signer = CloudFrontSigner(KEY_ID, rsa_signer)
    return signer.generate_presigned_url(url, date_less_than=expire_date)
```

Use for serving private content via CDN.

---

## Direct Browser Upload Flow (Complete Example)

### Backend
```python
@app.post("/files/upload-url")
async def get_upload_url(req: UploadRequest, user=Depends(get_user)):
    # Validate
    if req.size > MAX_SIZE:
        raise HTTPException(413)
    if not req.content_type.startswith("image/"):
        raise HTTPException(415)

    key = f"users/{user.id}/{uuid.uuid4()}-{req.filename}"

    # Generate URL
    url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": "my-bucket",
            "Key": key,
            "ContentType": req.content_type,
        },
        ExpiresIn=3600
    )

    # Store pending record
    file_id = uuid.uuid4()
    await db.execute(
        "INSERT INTO files (id, user_id, filename, key, status) "
        "VALUES ($1, $2, $3, $4, 'pending')",
        file_id, user.id, req.filename, key
    )

    return {
        "file_id": str(file_id),
        "upload_url": url,
        "key": key
    }

@app.post("/files/{file_id}/complete")
async def complete_upload(file_id: UUID, user=Depends(get_user)):
    file = await db.fetch_one("SELECT * FROM files WHERE id = $1", file_id)
    if file.user_id != user.id: raise HTTPException(403)

    # Verify upload happened
    try:
        head = s3.head_object(Bucket="my-bucket", Key=file.key)
        size = head["ContentLength"]
    except s3.exceptions.NoSuchKey:
        raise HTTPException(400, "File not uploaded")

    await db.execute(
        "UPDATE files SET status = 'uploaded', size_bytes = $1 WHERE id = $2",
        size, file_id
    )
    return {"status": "complete"}
```

### Frontend
```javascript
async function uploadFile(file) {
    // 1. Get presigned URL
    const initResp = await fetch("/files/upload-url", {
        method: "POST",
        body: JSON.stringify({
            filename: file.name,
            size: file.size,
            content_type: file.type
        })
    });
    const { file_id, upload_url } = await initResp.json();

    // 2. Upload directly to S3
    await fetch(upload_url, {
        method: "PUT",
        headers: { "Content-Type": file.type },
        body: file
    });

    // 3. Notify server
    await fetch(`/files/${file_id}/complete`, { method: "POST" });
}
```

---

## Common Pitfalls

### 1. Server-Side encryption + presigned PUT
If bucket policy requires SSE, signed PUT URL needs the encryption header:
```python
url = s3.generate_presigned_url(
    "put_object",
    Params={
        "Bucket": bucket,
        "Key": key,
        "ServerSideEncryption": "AES256",
    }
)
# Client must include:  x-amz-server-side-encryption: AES256
```

### 2. Long-lived URLs in logs / Slack
URLs grant access. Don't share via logs.

### 3. No origin check
Browser uploads can be initiated from any site. Add CORS to bucket.

### 4. Forgotten incomplete multiparts
Bills accumulate. Lifecycle rule.

### 5. Bucket public by mistake
Anyone can upload/download. Use Block Public Access + bucket policy.

### 6. Wrong Content-Type on PUT
Client uploads jpg but says content_type=image/png → confused browsers.

---

## Cost Optimization

### Storage classes
| Class | Cost | Use |
|---|---|---|
| Standard | $0.023/GB/month | Hot data |
| Standard-IA | $0.0125/GB | Infrequent |
| One-Zone-IA | $0.01/GB | Re-creatable |
| Glacier Instant | $0.004/GB | Archive, < 90 day |
| Glacier Flexible | $0.0036/GB | Archive, retrieval mins |
| Glacier Deep | $0.00099/GB | Long-term, retrieval hours |

Use lifecycle rules to transition.

### Transfer costs
- Upload to S3: free.
- Download from S3 to internet: $0.09/GB.
- S3 → CloudFront → user: $0.085/GB (cheaper).

For high-volume serving: always front with CloudFront.

---

## TL;DR

- Presigned URLs eliminate proxying file bytes through your server.
- Generate server-side; expire short (15min-1h).
- Use PUT for simple uploads, POST for conditional uploads, multipart for >5GB.
- CloudFront in front of S3 for public serving.
- Bucket-level: Block Public Access ON; access only via signed URLs.
- Use lifecycle rules to transition cold data.
- Validate content-type + size at both client and bucket policy level.
- Clean up orphan multipart uploads.
