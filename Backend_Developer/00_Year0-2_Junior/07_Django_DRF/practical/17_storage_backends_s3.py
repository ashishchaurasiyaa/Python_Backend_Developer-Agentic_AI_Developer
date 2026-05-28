"""
Storage Backends — S3 + Presigned URLs — Production Patterns
"""

# ==========================================================================
# 1. CUSTOM STORAGE BACKENDS
# ==========================================================================
"""
# core/storages.py — pip install django-storages[boto3]
"""

from storages.backends.s3 import S3Storage


class PublicMediaStorage(S3Storage):
    """Public assets — avatars, thumbnails. Served via CloudFront."""
    location = 'public'
    default_acl = 'public-read'
    file_overwrite = False
    querystring_auth = False
    custom_domain = 'cdn.example.com'


class PrivateMediaStorage(S3Storage):
    """Private files — invoices, tax docs. Signed URLs always."""
    location = 'private'
    default_acl = 'private'
    file_overwrite = False
    custom_domain = None         # use S3 endpoint for signing
    querystring_auth = True
    querystring_expire = 600     # 10 min


class StaticStorage(S3Storage):
    """Collected static files."""
    location = 'static'
    default_acl = 'public-read'
    file_overwrite = True
    querystring_auth = False


# ==========================================================================
# 2. MODEL USAGE
# ==========================================================================

# from django.db import models
# from core.storages import PublicMediaStorage, PrivateMediaStorage
# from uuid import uuid4
#
#
# def avatar_upload_to(instance, filename):
#     ext = filename.rsplit('.', 1)[-1]
#     return f'avatars/{instance.user_id}/{uuid4()}.{ext}'
#
#
# class Avatar(models.Model):
#     user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
#     image = models.ImageField(
#         storage=PublicMediaStorage(),
#         upload_to=avatar_upload_to,
#     )
#     uploaded_at = models.DateTimeField(auto_now_add=True)
#
#
# class TaxDocument(models.Model):
#     user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
#     file = models.FileField(
#         storage=PrivateMediaStorage(),
#         upload_to='tax/%Y/',
#     )
#     year = models.IntegerField()
#     size = models.IntegerField()         # cached — avoid HEAD on each access
#     content_type = models.CharField(max_length=100)


# ==========================================================================
# 3. PRESIGNED PUT URL (Frontend uploads directly)
# ==========================================================================

import boto3
from botocore.config import Config
from django.conf import settings


def get_s3_client():
    return boto3.client(
        's3',
        region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1'),
        config=Config(signature_version='s3v4'),
    )


def generate_presigned_put_url(key, content_type, expires_in=300):
    """Returns URL the frontend can PUT to (HTTP PUT, single object)."""
    client = get_s3_client()
    return client.generate_presigned_url(
        ClientMethod='put_object',
        Params={
            'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
            'Key': key,
            'ContentType': content_type,
            'ServerSideEncryption': 'AES256',
        },
        ExpiresIn=expires_in,
    )


# ==========================================================================
# 4. PRESIGNED POST (Browser form upload with conditions)
# ==========================================================================

def generate_presigned_post(
    key,
    content_type,
    max_size=10 * 1024 * 1024,
    expires_in=300,
):
    """
    Returns {url, fields} that frontend uses in a multipart form POST.
    Supports policy conditions (size limit, content-type whitelist).
    """
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
            # Force key prefix to prevent overwrite of others' files
            ['starts-with', '$key', 'uploads/'],
        ],
        ExpiresIn=expires_in,
    )


# ==========================================================================
# 5. DRF VIEWS — Direct Upload Flow
# ==========================================================================

# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated
# from uuid import uuid4
#
#
# ALLOWED_TYPES = {
#     'image/jpeg': 'jpg',
#     'image/png': 'png',
#     'application/pdf': 'pdf',
# }
# MAX_SIZE = 50 * 1024 * 1024  # 50 MB
#
#
# class UploadInitView(APIView):
#     """Frontend calls this to get presigned URL."""
#     permission_classes = [IsAuthenticated]
#
#     def post(self, request):
#         content_type = request.data.get('content_type')
#         filename = request.data.get('filename', '')
#
#         if content_type not in ALLOWED_TYPES:
#             return Response({'error': 'Invalid type'}, status=400)
#
#         ext = ALLOWED_TYPES[content_type]
#         key = f'uploads/{request.user.id}/{uuid4()}.{ext}'
#
#         post_data = generate_presigned_post(key, content_type, max_size=MAX_SIZE)
#         return Response({
#             'upload': post_data,
#             'key': key,
#         })
#
#
# class UploadCompleteView(APIView):
#     """Frontend calls after S3 upload to register in DB."""
#     permission_classes = [IsAuthenticated]
#
#     def post(self, request):
#         key = request.data.get('key')
#         if not key or not key.startswith(f'uploads/{request.user.id}/'):
#             return Response({'error': 'Invalid key'}, status=400)
#
#         # Verify exists in S3
#         client = get_s3_client()
#         try:
#             head = client.head_object(
#                 Bucket=settings.AWS_STORAGE_BUCKET_NAME,
#                 Key=key,
#             )
#         except client.exceptions.NoSuchKey:
#             return Response({'error': 'Not found in S3'}, status=404)
#
#         # Create DB record
#         doc = UserDocument.objects.create(
#             user=request.user,
#             s3_key=key,
#             size=head['ContentLength'],
#             content_type=head['ContentType'],
#         )
#         return Response({'id': doc.id})


# ==========================================================================
# 6. DOWNLOAD VIEW — Signed URL Generation
# ==========================================================================

# class DocumentDownloadView(APIView):
#     permission_classes = [IsAuthenticated]
#
#     def get(self, request, doc_id):
#         doc = get_object_or_404(UserDocument, id=doc_id, user=request.user)
#         # file.url is already presigned (querystring_auth=True)
#         return Response({'url': doc.file.url, 'expires_in': 600})


# ==========================================================================
# 7. POST_DELETE SIGNAL — Clean Up S3 Files
# ==========================================================================

from django.db.models.signals import post_delete
from django.dispatch import receiver


# @receiver(post_delete, sender=UserDocument)
def delete_s3_file_on_model_delete(sender, instance, **kwargs):
    """Best-effort delete from S3. Use scheduled cleanup as backup."""
    if instance.file and instance.file.name:
        instance.file.delete(save=False)


# ==========================================================================
# 8. SCHEDULED ORPHAN CLEANUP (mgmt command)
# ==========================================================================
"""
File: ops/management/commands/cleanup_s3_orphans.py
"""

from django.core.management.base import BaseCommand


class CleanupOrphansCommand(BaseCommand):
    help = "Delete S3 files not referenced in DB (orphans)"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--prefix', default='uploads/')

    def handle(self, *args, **options):
        client = get_s3_client()

        # Get all DB-referenced keys
        # from blog.models import UserDocument
        # db_keys = set(UserDocument.objects.values_list('s3_key', flat=True))
        db_keys = set()

        # List all S3 keys under prefix
        s3_keys = set()
        paginator = client.get_paginator('list_objects_v2')
        for page in paginator.paginate(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Prefix=options['prefix'],
        ):
            for obj in page.get('Contents', []):
                s3_keys.add(obj['Key'])

        orphans = s3_keys - db_keys
        self.stdout.write(f"Found {len(orphans)} orphans")

        if options['dry_run']:
            for o in list(orphans)[:10]:
                self.stdout.write(f"  Would delete: {o}")
            return

        # Batch delete (1000 max per call)
        orphans_list = list(orphans)
        for i in range(0, len(orphans_list), 1000):
            batch = orphans_list[i:i + 1000]
            client.delete_objects(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Delete={'Objects': [{'Key': k} for k in batch]},
            )
            self.stdout.write(f"Deleted batch of {len(batch)}")


# ==========================================================================
# 9. S3 BUCKET POLICY (place in bucket settings, not Django)
# ==========================================================================
"""
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyUnencrypted",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::media.example.com/*",
      "Condition": {
        "StringNotEquals": {"s3:x-amz-server-side-encryption": "AES256"}
      }
    },
    {
      "Sid": "DenyHTTPPublic",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": "arn:aws:s3:::media.example.com/*",
      "Condition": {"Bool": {"aws:SecureTransport": "false"}}
    }
  ]
}

# CORS (allow browser PUT/POST from your app domain)
[
  {
    "AllowedOrigins": ["https://app.example.com"],
    "AllowedMethods": ["GET", "PUT", "POST", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]

# Lifecycle (auto-delete incomplete multipart, archive old files)
{
  "Rules": [
    {
      "ID": "abort-multipart",
      "Status": "Enabled",
      "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
    },
    {
      "ID": "archive-old",
      "Status": "Enabled",
      "Filter": {"Prefix": "uploads/"},
      "Transitions": [{"Days": 90, "StorageClass": "STANDARD_IA"},
                      {"Days": 180, "StorageClass": "GLACIER"}]
    }
  ]
}
"""
