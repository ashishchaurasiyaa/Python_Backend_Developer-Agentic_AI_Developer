# File-Based Storage

## Quick Reference Card
```
File Storage    → Files/blobs as-is — S3, local filesystem, NFS
Block Storage   → Raw blocks of data — EBS, SAN (for DBs, VMs)
Object Storage  → Files + metadata + unique key — S3, GCS (unlimited scale)
NFS             → Network File System — remote mount point, shared access
CDN             → Content Delivery Network — cached files at edge nodes
Interview hook  → "Youngman certificates → S3 | Invoices PDF → S3 | Media → CloudFront CDN"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 File Storage Kya Hai?

**Analogy: Almari ke drawers**

- **Local filesystem** = Teri apni almari — sirf tu access kar sakta hai, ek hi machine pe
- **NFS** = Shared almari in office — multiple log access kar sakte hain, but almari ek jagah hai
- **S3 (Object Storage)** = Cloud warehouse — unlimited jagah, internet se accessible, reliable, global

```
Storage Types:
─────────────────────────────────────────────────────────────────
Type          Example          Access      Scale    Use Case
─────────────────────────────────────────────────────────────────
Local File    /var/uploads     localhost   Limited  Dev only
NFS           mounted drive    LAN/WAN     Medium   Office share
Block (EBS)   /dev/sdb1        Single EC2  Good     DB data files
Object (S3)   s3://bucket/key  HTTP API    Unlimited Media, backups
CDN           cdn.example.com  Global edge Unlimited Static assets
─────────────────────────────────────────────────────────────────
```

---

### 1.2 Local File System — Problems at Scale

```
LOCAL FILESYSTEM:
  /var/app/media/
    ├── invoices/
    │   ├── INV-001.pdf
    │   └── INV-002.pdf
    ├── certificates/
    │   └── CERT-001.pdf
    └── uploads/
        └── company_logo.png

PROBLEMS:
  1. Single server → SPOF
     EC2 instance crashes → ALL files lost!
  
  2. Horizontal scaling impossible
     App Server 1: /var/media/logo.png exists
     App Server 2: /var/media/logo.png DOESN'T EXIST!
     User uploads to Server 1, requests hit Server 2 → 404!
  
  3. Disk fills up → Manual intervention needed
  
  4. No built-in CDN → Slow delivery to distant users
  
  5. Backup is developer's responsibility
  
  Django default (BAD for production):
  MEDIA_ROOT = '/var/www/media/'
  MEDIA_URL = '/media/'
  # Upload → local disk
  # If server dies → files die with it
```

---

### 1.3 Object Storage — AWS S3

```
OBJECT STORAGE CONCEPT:
  Unlike filesystem (folders/files/paths):
  → Objects stored with unique KEY in flat namespace
  → No real "folders" (/ is just part of key string)
  → Each object: Key + Data (bytes) + Metadata + Version
  
  s3://youngman-prod/invoices/2024/01/INV-001.pdf
         bucket      ←────── key ──────────────►
  
  Operations:
    PUT s3://bucket/key   → Store object
    GET s3://bucket/key   → Retrieve object
    DELETE s3://bucket/key → Delete
    LIST s3://bucket/prefix/ → List objects with prefix

WHY S3 IS GOOD:
  ✓ Virtually unlimited storage
  ✓ 11 nines (99.999999999%) durability — 3 copies in 3 AZs
  ✓ 99.99% availability
  ✓ Automatic versioning
  ✓ Built-in encryption
  ✓ Fine-grained access control (IAM + bucket policies)
  ✓ Lifecycle rules (move to Glacier after 90 days)
  ✓ Works with CDN (CloudFront)
  ✓ No capacity planning needed
  ✓ Pay only for what you use (~$0.023/GB/month)
```

---

### 1.4 Django + S3 Integration

```python
# pip install django-storages boto3

# settings.py
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
STATICFILES_STORAGE = 'storages.backends.s3boto3.StaticS3Boto3Storage'

AWS_STORAGE_BUCKET_NAME = 'youngman-prod'
AWS_S3_REGION_NAME = 'ap-south-1'      # Mumbai
AWS_S3_CUSTOM_DOMAIN = 'd1234abcd.cloudfront.net'  # CDN domain

# Access control
AWS_DEFAULT_ACL = 'private'             # Private by default
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',    # CDN cache 24 hours
}

# Optional: Separate buckets for different media
AWS_STATIC_LOCATION = 'static'         # s3://bucket/static/
AWS_MEDIA_LOCATION = 'media'           # s3://bucket/media/
AWS_PRIVATE_LOCATION = 'private'       # s3://bucket/private/ (invoices, certs)

# Models — file fields work automatically
class Invoice(models.Model):
    pdf_file = models.FileField(
        upload_to='invoices/%Y/%m/',   # s3://bucket/invoices/2024/01/filename.pdf
        null=True, blank=True
    )
    
    def get_download_url(self):
        """Generate pre-signed URL for secure download"""
        import boto3
        s3 = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME)
        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': str(self.pdf_file),
            },
            ExpiresIn=3600  # URL valid for 1 hour
        )
        return url

# Generating and uploading certificate
from io import BytesIO
import weasyprint
import boto3

def generate_certificate(booking):
    """Generate PDF and upload directly to S3"""
    html = render_to_string('certificate.html', {'booking': booking})
    
    # Generate PDF in memory (not local disk!)
    pdf_buffer = BytesIO()
    weasyprint.HTML(string=html).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    
    # Upload to S3
    s3 = boto3.client('s3')
    key = f'certificates/{booking.id}/certificate.pdf'
    s3.upload_fileobj(
        pdf_buffer,
        settings.AWS_STORAGE_BUCKET_NAME,
        key,
        ExtraArgs={
            'ContentType': 'application/pdf',
            'ServerSideEncryption': 'AES256',  # Encrypted at rest
        }
    )
    
    return f's3://{settings.AWS_STORAGE_BUCKET_NAME}/{key}'
```

---

### 1.5 Pre-signed URLs — Secure File Access

```
PROBLEM: Private file kaise serve karein securely?
  - S3 bucket is PRIVATE (no public access)
  - User should be able to download THEIR invoice
  - But not someone else's invoice

SOLUTION: Pre-signed URLs
  - Time-limited URL (1 hour, 24 hours)
  - Cryptographically signed by AWS IAM credentials
  - Anyone with the URL can download
  - URL expires after specified time

FLOW:
  1. User requests: "Download my invoice"
  2. Django checks: Is user allowed? (yes)
  3. Django generates: pre-signed S3 URL (valid 1 hour)
  4. Django returns: URL to client
  5. Client downloads directly from S3
  
  App Server                S3
  ┌───────────────┐         ┌───────────────┐
  │ User: "Invoice"│        │ Private bucket │
  │ Auth check ✓  │         │ invoices/001  │
  │ Generate URL  │         │               │
  │ Return URL ──────────────────────────── │
  └───────────────┘         └───────────────┘
                                      │
                   Client ←──── Download PDF (1hr window)

CODE:
  def invoice_download(request, invoice_id):
      invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
      
      s3 = boto3.client('s3', region_name='ap-south-1')
      url = s3.generate_presigned_url(
          ClientMethod='get_object',
          Params={
              'Bucket': 'youngman-prod',
              'Key': f'invoices/{invoice.pdf_filename}',
          },
          ExpiresIn=3600  # 1 hour
      )
      return JsonResponse({'download_url': url})
```

---

### 1.6 CDN — Content Delivery Network

```
PROBLEM: S3 is in Mumbai, user is in London → slow download

SOLUTION: CloudFront CDN
  S3 (origin) → CloudFront (125+ edge locations worldwide)
  
  User in London:
  → Request certificate.pdf
  → CloudFront London edge: "Do I have this?" 
  → NO (first time) → Fetch from S3 Mumbai → Cache at London edge
  → YES (subsequent) → Serve from London edge (fast!)
  
  LONDON USER: 50ms (London edge)
  vs
  LONDON USER without CDN: 150ms (Mumbai S3)

  ┌──────────────────────────────────────────────────────┐
  │                    CloudFront                         │
  │  London edge  Mumbai edge  Singapore edge  NYC edge   │
  │      │             │              │           │        │
  └──────┼─────────────┼──────────────┼───────────┼───────┘
         │             │              │           │
         └─────────────┴──────────────┴───────────┘
                              │
                        S3 (origin)

Static assets cached: JS, CSS, images, PDFs, certificates
API responses: Usually NOT cached (dynamic, user-specific)

Django + CloudFront:
  # settings.py
  AWS_S3_CUSTOM_DOMAIN = 'd1234abcd.cloudfront.net'
  
  # All S3 URLs automatically use CDN domain:
  # https://d1234abcd.cloudfront.net/static/styles.css
  # Instead of:
  # https://youngman-prod.s3.amazonaws.com/static/styles.css
```

---

### 1.7 Block Storage vs Object Storage

```
BLOCK STORAGE (AWS EBS):
  Low-level storage → raw disk blocks
  OS mounts as /dev/sdb1 → formatted as ext4, XFS
  Used for: DB data files, VM disk images
  
  Characteristics:
  - Attached to single EC2 (like hard drive)
  - Low latency, high IOPS
  - Expensive
  - Max ~16TB per volume
  - Must pre-provision size
  
  Use: PostgreSQL data directory sits on EBS
  /var/lib/postgresql/data → EBS volume

OBJECT STORAGE (S3):
  High-level storage → files via HTTP API
  No mounting needed — use boto3 SDK
  Used for: Media files, backups, static assets
  
  Characteristics:
  - Accessible from anywhere (HTTP)
  - Higher latency than block (but massively scalable)
  - Cheaper (10x less per GB)
  - Unlimited size
  - Pay per use
  
  Use: Django MEDIA_ROOT → S3 bucket

File vs Block vs Object:
  File storage (NFS): Hierarchical, shared access, POSIX compliant
  Block storage (EBS): Raw blocks, fastest for DB
  Object storage (S3): HTTP-based, metadata-rich, unlimited scale
```

---

### 1.8 Ashish ke projects mein

```
Youngman:
  Invoice PDFs     → S3 (private bucket, pre-signed URLs for download)
  Certificate PDFs → S3 (generated on-demand, cached key in Redis)
  Company logos    → S3 (static assets served via CloudFront CDN)
  Django static    → S3 + CloudFront (CSS, JS — global fast delivery)
  
  Database files → EBS (attached to RDS instance, not S3)
  
  Local filesystem: NOTHING (critical files go to S3)
  
  Why S3 for certificates:
    - WeasyPrint generates PDF → BytesIO (in-memory)
    - Upload to S3 directly
    - Never touches EC2 disk
    - Multiple app servers → all read same S3 files
    - Horizontal scaling works perfectly!
  
  Pre-signed URL pattern for invoices:
    - Invoice in S3 private bucket
    - API endpoint generates 1-hour pre-signed URL
    - Frontend redirects user to URL
    - User downloads directly from S3 (no bandwidth on app server)

Niroskos:
  Booking documents → S3
  Tour media (photos, videos) → S3 + CloudFront
  User profile photos → S3 + CloudFront
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definitions

> **File-Based Storage**: Storing unstructured binary data (files) as objects or in a filesystem. Three main types: (1) Local filesystem — single machine, limited. (2) NFS (Network File System) — shared filesystem over network. (3) Object Storage (S3) — key-value store for files via HTTP API, unlimited scale.

> **Object Storage (S3)**: A storage paradigm where each file is an object with a unique key, the binary data, and associated metadata. No filesystem hierarchy — the key is the full path. Provides unlimited scale, high durability (99.999999999%), and HTTP access. AWS S3, Google Cloud Storage, Azure Blob Storage.

---

### 2.2 Storage Types Comparison

| Feature | Local FS | NFS | EBS | S3 (Object) |
|---------|----------|-----|-----|-------------|
| Access | Single server | Network mount | Single EC2 | HTTP API |
| Scale | Limited (disk) | Limited (NAS) | Up to 64TB | Unlimited |
| Durability | Low (no HA) | Medium | High (snapshots) | 11 nines |
| Latency | ~0.1ms | ~2-5ms | ~0.5ms | ~50-100ms |
| Cost | Server disk | NAS cost | ~$0.10/GB/mo | ~$0.023/GB/mo |
| Horizontal scale | No | Limited | No | Yes |
| CDN integration | No | No | No | Yes (CloudFront) |
| Best for | Dev, temp files | Legacy apps | DB data | Media, backups, static |

---

### 2.3 S3 Storage Classes (Cost Optimization)

```
S3 Standard:         $0.023/GB — Active data, frequent access
S3 Standard-IA:      $0.0125/GB — Infrequent access (monthly reports)
S3 One Zone-IA:      $0.01/GB  — Single AZ, less durable
S3 Glacier Instant:  $0.004/GB — Archives, retrieval in ms
S3 Glacier Flexible: $0.0036/GB — Deep archive, retrieval minutes-hours
S3 Intelligent-Tiering: Auto moves between tiers based on access

Lifecycle Policy:
  - Invoices older than 90 days → move to S3-IA (save 45%)
  - Archives older than 1 year → move to Glacier (save 80%)
  
  s3_lifecycle_rule = {
      'Transitions': [
          {'Days': 90, 'StorageClass': 'STANDARD_IA'},
          {'Days': 365, 'StorageClass': 'GLACIER'},
      ]
  }
```

---

### 2.4 Real Project Answer

> "In Youngman, we migrated from local filesystem uploads to S3 early on. The trigger was adding a second EC2 instance — suddenly uploaded files weren't accessible across servers. We use django-storages with S3Boto3Storage backend. All MEDIA_ROOT operations are transparently redirected to S3. Invoice PDFs are stored in a private S3 bucket and served via pre-signed URLs with 1-hour expiry — the user gets a time-limited direct download URL, which also means zero bandwidth cost on our app servers. Static assets (CSS, JS, images) are served via CloudFront CDN in front of S3, giving us global fast delivery. Certificate generation uses BytesIO to create the PDF in memory and upload directly to S3, never touching the EC2 disk."

---

### 2.5 Common Follow-up Q&A

**Q1: What is the difference between S3 and a database for storing files?**
> "Databases store structured, queryable data. S3 stores binary blobs. Don't store large files in DB columns — it increases DB size, slows backups, and consumes DB connections for file transfers. The standard pattern: store the file in S3, store the S3 key reference in the database column. This way the DB stays lean and fast, while files benefit from S3's durability and CDN acceleration. In Django: `FileField` stores the S3 key as a string in the DB column, and the actual bytes are in S3."

**Q2: How do you handle large file uploads efficiently?**
> "For large files (videos, large datasets), we use S3 Multipart Upload or pre-signed PUT URLs. With pre-signed PUT: the client requests an upload URL from our API, we generate a pre-signed S3 PUT URL with specified Content-Type and Content-Length, the client uploads directly to S3 from their browser — no server bandwidth used. For very large files (5GB+), we use multipart upload: split file into parts, upload in parallel, S3 assembles them. This is done automatically by boto3's `upload_fileobj` with `TransferConfig`. The key is the client goes directly to S3 — our server just coordinates with presigned URLs."

**Q3: How do you handle file versioning?**
> "S3 versioning can be enabled per bucket — each PUT creates a new version rather than overwriting. This gives us accidental deletion protection and easy rollback. For invoice files specifically, we include the version in the key itself: `invoices/2024/01/INV-001-v2.pdf` rather than relying on S3 versioning, because we want the version to be explicit and queryable in our DB. For media uploads where versioning matters (profile photos), we use S3 versioning. For certificate regeneration, we generate a new key and update the DB reference — old certificate remains in S3 for audit purposes."

---

## Interview Cheat Sheet

```
Storage Types:
  Local FS: Fast, single machine, SPOF, no horizontal scaling
  EBS: Block storage, single EC2, DB files
  NFS: Network mount, shared, legacy apps
  S3: Object storage, unlimited, HTTP API, 11 nines durability

S3 Key Features:
  - Flat namespace (key = full path)
  - 11 nines durability (3 copies, 3 AZs)
  - Private/Public ACL
  - Pre-signed URLs (time-limited access)
  - Lifecycle rules (auto-transition to cheaper tiers)
  - Versioning
  - CDN integration (CloudFront)

Django + S3:
  DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
  → All FileField/ImageField automatically uses S3

Pre-signed URL pattern:
  Private file → API endpoint → auth check → generate signed URL
  → Client downloads directly from S3 (no server bandwidth)

S3 Storage Classes (cost optimization):
  Standard → IA (90 days) → Glacier (1 year)
  Auto via lifecycle policies

My project:
  Invoices: S3 private + presigned URLs
  Certificates: Generate in BytesIO → upload to S3
  Static: S3 + CloudFront CDN
  Local FS: NOTHING (stateless EC2)
```
