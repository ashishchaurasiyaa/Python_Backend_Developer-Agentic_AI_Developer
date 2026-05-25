"""
DRF File Uploads — Production Patterns

Multipart, validated, presigned S3 direct upload, multipart S3, chunked resumable.
"""

# ==========================================================================
# 1. SETTINGS — Streaming-friendly defaults
# ==========================================================================
"""
# settings.py
FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
    # Remove MemoryFileUploadHandler to force disk streaming
]

FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024   # 2 MB — files larger go to disk
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100
DATA_UPLOAD_MAX_NUMBER_FILES = 5
FILE_UPLOAD_PERMISSIONS = 0o644
"""


# ==========================================================================
# 2. MODEL
# ==========================================================================

from django.db import models
from uuid import uuid4


def safe_upload_path(instance, filename):
    """Generates UUID-prefixed path — no client-controlled paths."""
    import os, re
    safe = re.sub(r'[^a-zA-Z0-9._-]', '_', os.path.basename(filename))
    return f'docs/{instance.uploaded_by_id}/{uuid4()}-{safe}'


class Document(models.Model):
    uploaded_by = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    title = models.CharField(max_length=200, blank=True)
    file = models.FileField(upload_to=safe_upload_path, max_length=500)

    # For S3 direct uploads — store reference
    s3_key = models.CharField(max_length=500, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.BigIntegerField(default=0)

    # Virus scan state
    scan_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('scanning', 'Scanning'),
            ('clean', 'Clean'),
            ('infected', 'Infected'),
            ('failed', 'Failed'),
        ],
        default='pending',
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'blog'


# ==========================================================================
# 3. VALIDATION HELPERS
# ==========================================================================

# pip install python-magic Pillow
import magic
from PIL import Image
from rest_framework.exceptions import ValidationError


ALLOWED_MIMES = {
    'image/jpeg': ('.jpg', '.jpeg'),
    'image/png': ('.png',),
    'image/webp': ('.webp',),
    'application/pdf': ('.pdf',),
}

MAX_SIZE_BY_TYPE = {
    'image/jpeg': 10 * 1024 * 1024,
    'image/png': 10 * 1024 * 1024,
    'image/webp': 10 * 1024 * 1024,
    'application/pdf': 50 * 1024 * 1024,
}

# Image bomb protection
Image.MAX_IMAGE_PIXELS = 100_000_000


def validate_upload(uploaded_file):
    """Comprehensive validation — call from serializer.validate_file."""
    # Size
    if uploaded_file.size == 0:
        raise ValidationError('Empty file')

    # Read first 2KB for libmagic (need to seek back)
    head = uploaded_file.read(2048)
    uploaded_file.seek(0)

    # Detect actual MIME
    detected = magic.from_buffer(head, mime=True)
    if detected not in ALLOWED_MIMES:
        raise ValidationError(f'Unsupported type: {detected}')

    # Cross-check Content-Type from request
    if uploaded_file.content_type and uploaded_file.content_type != detected:
        raise ValidationError(
            f'Content-Type mismatch: claimed {uploaded_file.content_type}, detected {detected}'
        )

    # Extension check
    name_lower = uploaded_file.name.lower()
    allowed_exts = ALLOWED_MIMES[detected]
    if not any(name_lower.endswith(ext) for ext in allowed_exts):
        raise ValidationError(f'Extension does not match content (expected {allowed_exts})')

    # Size per type
    max_size = MAX_SIZE_BY_TYPE.get(detected, 5 * 1024 * 1024)
    if uploaded_file.size > max_size:
        raise ValidationError(f'File too large ({uploaded_file.size} > {max_size})')

    # Image-specific validation
    if detected.startswith('image/'):
        validate_image(uploaded_file)


def validate_image(uploaded_file, max_dimensions=(4000, 4000)):
    """Pillow-based image validation."""
    try:
        img = Image.open(uploaded_file)
        img.verify()
    except Exception as e:
        raise ValidationError(f'Invalid image: {e}')
    uploaded_file.seek(0)

    img = Image.open(uploaded_file)
    if img.width > max_dimensions[0] or img.height > max_dimensions[1]:
        raise ValidationError(f'Dimensions {img.width}x{img.height} exceed limit')
    uploaded_file.seek(0)


# ==========================================================================
# 4. SERIALIZER + VIEWSET (multipart upload)
# ==========================================================================

from rest_framework import serializers, viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'content_type', 'size', 'scan_status', 'uploaded_at']
        read_only_fields = ['id', 'content_type', 'size', 'scan_status', 'uploaded_at']

    def validate_file(self, value):
        validate_upload(value)
        return value

    def create(self, validated_data):
        f = validated_data['file']
        doc = Document.objects.create(
            uploaded_by=validated_data.get('uploaded_by') or self.context['request'].user,
            title=validated_data.get('title', ''),
            file=f,
            content_type=f.content_type or '',
            size=f.size,
            scan_status='pending',
        )
        # Async virus scan
        # from blog.tasks import virus_scan_document
        # virus_scan_document.delay(doc.id)
        return doc


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(uploaded_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


# ==========================================================================
# 5. S3 PRESIGNED PUT (direct browser → S3, < 5 GB)
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


class UploadInitView(APIView):
    """Step 1: client requests upload URL."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        content_type = request.data.get('content_type')
        filename = request.data.get('filename', 'file')
        claimed_size = int(request.data.get('size', 0))

        if content_type not in ALLOWED_MIMES:
            return Response({'error': 'Invalid content_type'}, status=400)

        max_size = MAX_SIZE_BY_TYPE.get(content_type, 5 * 1024 * 1024)
        if claimed_size > max_size:
            return Response({'error': 'Too large'}, status=400)

        key = f'uploads/{request.user.id}/{uuid4()}'
        client = get_s3_client()
        url = client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': key,
                'ContentType': content_type,
                'ServerSideEncryption': 'AES256',
            },
            ExpiresIn=300,
        )
        return Response({
            'upload_url': url,
            'key': key,
            'method': 'PUT',
            'headers': {
                'Content-Type': content_type,
                'x-amz-server-side-encryption': 'AES256',
            },
            'expires_in': 300,
        })


class UploadCompleteView(APIView):
    """Step 2: client notifies after upload."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        key = request.data.get('key', '')
        # Validate key belongs to user
        prefix = f'uploads/{request.user.id}/'
        if not key.startswith(prefix):
            return Response({'error': 'Invalid key'}, status=400)

        client = get_s3_client()
        try:
            head = client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
        except client.exceptions.ClientError:
            return Response({'error': 'File not found'}, status=404)

        # Post-upload MIME re-check (S3 saves Content-Type from PUT)
        if head['ContentType'] not in ALLOWED_MIMES:
            client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
            return Response({'error': 'Invalid content type'}, status=400)

        max_size = MAX_SIZE_BY_TYPE.get(head['ContentType'], 5 * 1024 * 1024)
        if head['ContentLength'] > max_size:
            client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
            return Response({'error': 'File too large'}, status=400)

        doc = Document.objects.create(
            uploaded_by=request.user,
            title=request.data.get('title', ''),
            s3_key=key,
            content_type=head['ContentType'],
            size=head['ContentLength'],
            scan_status='pending',
        )

        # Async virus scan
        # from blog.tasks import virus_scan_document
        # virus_scan_document.delay(doc.id)

        return Response(DocumentSerializer(doc).data, status=201)


# ==========================================================================
# 6. S3 MULTIPART UPLOAD (>100 MB, resumable)
# ==========================================================================

class MultipartInitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        content_type = request.data.get('content_type')
        if content_type not in ALLOWED_MIMES:
            return Response({'error': 'Invalid type'}, status=400)

        key = f'uploads/{request.user.id}/{uuid4()}'
        client = get_s3_client()
        resp = client.create_multipart_upload(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=key,
            ContentType=content_type,
            ServerSideEncryption='AES256',
        )

        return Response({
            'upload_id': resp['UploadId'],
            'key': key,
        })


class MultipartPartUrlView(APIView):
    """Get presigned URL for each part."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        key = request.data['key']
        prefix = f'uploads/{request.user.id}/'
        if not key.startswith(prefix):
            return Response({'error': 'Invalid key'}, status=400)

        client = get_s3_client()
        url = client.generate_presigned_url(
            'upload_part',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': key,
                'UploadId': request.data['upload_id'],
                'PartNumber': int(request.data['part_number']),
            },
            ExpiresIn=3600,
        )
        return Response({'url': url, 'method': 'PUT'})


class MultipartCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # parts = [{'ETag': '"abc..."', 'PartNumber': 1}, ...]
        client = get_s3_client()
        try:
            client.complete_multipart_upload(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=request.data['key'],
                UploadId=request.data['upload_id'],
                MultipartUpload={'Parts': request.data['parts']},
            )
        except client.exceptions.ClientError as e:
            return Response({'error': str(e)}, status=400)

        # Create DB record similar to UploadCompleteView
        head = client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=request.data['key'])
        doc = Document.objects.create(
            uploaded_by=request.user,
            s3_key=request.data['key'],
            content_type=head['ContentType'],
            size=head['ContentLength'],
        )
        return Response(DocumentSerializer(doc).data, status=201)


class MultipartAbortView(APIView):
    """Client cancelled — cleanup S3."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        client = get_s3_client()
        client.abort_multipart_upload(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=request.data['key'],
            UploadId=request.data['upload_id'],
        )
        return Response({'aborted': True})


# ==========================================================================
# 7. ASYNC VIRUS SCAN (Celery task)
# ==========================================================================

# from celery import shared_task
# import subprocess


# @shared_task
# def virus_scan_document(doc_id):
#     doc = Document.objects.get(pk=doc_id)
#     doc.scan_status = 'scanning'
#     doc.save(update_fields=['scan_status'])
#
#     # Download from S3 to tmp
#     import tempfile
#     client = get_s3_client()
#     with tempfile.NamedTemporaryFile() as tmp:
#         client.download_fileobj(
#             settings.AWS_STORAGE_BUCKET_NAME,
#             doc.s3_key,
#             tmp,
#         )
#         tmp.flush()
#         # ClamAV scan
#         result = subprocess.run(
#             ['clamdscan', '--no-summary', tmp.name],
#             capture_output=True,
#         )
#
#     if result.returncode == 0:
#         doc.scan_status = 'clean'
#     elif result.returncode == 1:
#         doc.scan_status = 'infected'
#         # Quarantine — move to quarantine bucket
#         client.copy_object(
#             Bucket='quarantine.example.com',
#             CopySource={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': doc.s3_key},
#             Key=doc.s3_key,
#         )
#         client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=doc.s3_key)
#     else:
#         doc.scan_status = 'failed'
#
#     doc.save(update_fields=['scan_status'])
