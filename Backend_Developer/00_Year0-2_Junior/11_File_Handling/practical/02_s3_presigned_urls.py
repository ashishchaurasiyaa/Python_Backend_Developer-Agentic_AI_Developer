"""
S3 Presigned URLs — Production Patterns
========================================
Covers every pattern from the theory doc:

  1.  S3 client setup (SigV4, region, config)
  2.  Presigned GET URL  (download — with optional forced filename)
  3.  Presigned PUT URL  (simple upload)
  4.  Presigned POST     (conditional upload — size / content-type guards)
  5.  Multipart upload   (large files > 5 GB — initiate / part URLs / complete)
  6.  Abort / cleanup    (orphan multipart protection)
  7.  FastAPI integration (init-upload + complete-upload endpoints)
  8.  CloudFront signed URL  (CDN layer for private content)
  9.  Encryption at rest helper
  10. URL TTL + security constants
  11. Pitfall guard utilities (SSE header check, content-type validator)

External dependencies (none installed = file is illustrative / importable):
    pip install boto3 botocore fastapi pydantic
    pip install cryptography          # CloudFront RSA signer

All code uses Python 3.9-safe typing (Optional[X] / List[X], not X | None).
No __main__ block — no live AWS credentials are required to import this module.
"""

# pip install boto3 botocore
import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# boto3 / botocore — imported lazily so the file parses cleanly even without
# the library installed.  In a real service, import at module level.
# ---------------------------------------------------------------------------
try:
    import boto3                          # type: ignore
    from botocore.config import Config    # type: ignore
    from botocore.exceptions import ClientError  # type: ignore
    _BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover
    boto3 = None      # type: ignore
    Config = None     # type: ignore
    ClientError = Exception  # type: ignore
    _BOTO3_AVAILABLE = False

log = logging.getLogger(__name__)


# ==========================================================================
# 1. CONSTANTS — TTL & SECURITY
# ==========================================================================

# Presigned URL expiry windows (seconds).
# Theory: "Never use the 7-day default; keep short."
TTL_DOWNLOAD: int = 3_600      # 1 hour  — safe for GET (download)
TTL_UPLOAD: int = 900           # 15 min  — narrower window for PUT / POST
TTL_MULTIPART_PART: int = 3_600 # 1 hour  — per-part during large uploads

MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024          # 5 MB presigned-POST default
MAX_MULTIPART_BYTES: int = 5 * 1024 * 1024 * 1024  # 5 GB — S3 single-PUT limit

ALLOWED_IMAGE_TYPES: List[str] = [
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
]


# ==========================================================================
# 2. S3 CLIENT SETUP
# ==========================================================================

def build_s3_client(
    region: str = "us-east-1",
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> Any:
    """
    Return a boto3 S3 client configured with Signature Version 4.

    SigV4 is mandatory for presigned URLs with server-side encryption and
    for buckets outside us-east-1.  Always specify region explicitly —
    auto-detection can produce wrong endpoints.

    Credentials: prefer IAM roles (EC2 / ECS / Lambda) so keys never appear
    in source code or environment variables.  Pass explicit keys only for
    local development against localstack.
    """
    if not _BOTO3_AVAILABLE:
        raise RuntimeError("boto3 is not installed — run: pip install boto3")

    kwargs: Dict[str, Any] = {
        "service_name": "s3",
        "region_name": region,
        "config": Config(signature_version="s3v4"),
    }
    if aws_access_key_id and aws_secret_access_key:
        kwargs["aws_access_key_id"] = aws_access_key_id
        kwargs["aws_secret_access_key"] = aws_secret_access_key

    return boto3.client(**kwargs)


# Module-level singleton (populated at import time when boto3 is present).
# Services that need a custom region should call build_s3_client() directly.
s3_client: Optional[Any] = build_s3_client() if _BOTO3_AVAILABLE else None


# ==========================================================================
# 3. PRESIGNED GET URL — DOWNLOAD
# ==========================================================================

def generate_download_url(
    bucket: str,
    key: str,
    expires_in: int = TTL_DOWNLOAD,
    filename_override: Optional[str] = None,
    client: Optional[Any] = None,
) -> str:
    """
    Generate a presigned GET URL so a client can download ``key`` from
    ``bucket`` directly from S3, bypassing the API server.

    ``filename_override`` sets the Content-Disposition header embedded in
    the signature, forcing the browser to save with the given filename
    instead of the S3 key path.

    Architecture:
        Without presigned URL: Client → API → S3 → API → Client
        With presigned URL:    Client → API → URL; Client → S3 directly

    API bandwidth = ~200 bytes (the URL).  S3 handles GB-scale transfers.
    """
    _client = client or s3_client
    params: Dict[str, Any] = {"Bucket": bucket, "Key": key}

    if filename_override:
        # Forces browser to prompt "Save As" with the specified filename.
        params["ResponseContentDisposition"] = (
            f'attachment; filename="{filename_override}"'
        )

    url: str = _client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in,
    )
    log.debug("Generated download URL for s3://%s/%s (ttl=%ds)", bucket, key, expires_in)
    return url


# ==========================================================================
# 4. PRESIGNED PUT URL — SIMPLE UPLOAD
# ==========================================================================

def generate_upload_url(
    bucket: str,
    key: str,
    content_type: str,
    expires_in: int = TTL_UPLOAD,
    server_side_encryption: Optional[str] = None,
    client: Optional[Any] = None,
) -> str:
    """
    Generate a presigned PUT URL so a client can upload a file directly to S3.

    Pitfall (theory doc §Common Pitfalls #1):
        If the bucket policy enforces SSE, the signed URL must include the
        encryption header; otherwise S3 rejects the upload with 403.
        The client must send the matching header:
            x-amz-server-side-encryption: AES256

    ``content_type`` must match what the client sends in the PUT request's
    Content-Type header — mismatch causes S3 to reject or serves with the
    wrong MIME type.
    """
    _client = client or s3_client
    params: Dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "ContentType": content_type,
    }

    if server_side_encryption:
        # AES256 (S3 managed) or "aws:kms" (KMS managed).
        params["ServerSideEncryption"] = server_side_encryption

    url: str = _client.generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=expires_in,
    )
    log.debug("Generated upload URL for s3://%s/%s", bucket, key)
    return url


def build_user_object_key(user_id: str, filename: str) -> str:
    """
    Construct an S3 key for user-uploaded content.

    Pattern: users/<user_id>/<uuid>-<sanitized_filename>

    The UUID prefix prevents collisions when the same filename is uploaded
    twice, and scatters objects across S3's internal shard boundaries.
    Theory: "For high-throughput uploads, randomize prefix."
    """
    safe_filename = filename.replace(" ", "-").lower()
    return f"users/{user_id}/{uuid.uuid4()}-{safe_filename}"


# ==========================================================================
# 5. PRESIGNED POST — CONDITIONAL UPLOAD
# ==========================================================================

def generate_presigned_post(
    bucket: str,
    key_prefix: str,
    content_type: str,
    max_size_bytes: int = MAX_UPLOAD_BYTES,
    expires_in: int = TTL_UPLOAD,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Generate a presigned POST with server-enforced conditions.

    More restrictive than a PUT URL: S3 validates each condition before
    accepting the upload.  Use this when you need to:
        - Cap upload size on the S3 side (not just client-side).
        - Restrict content-type to a prefix (e.g., "image/*").
        - Constrain the key to a specific prefix.

    Returns the dict that the client posts as multipart/form-data:
        {
            "url": "https://bucket.s3.amazonaws.com/",
            "fields": {
                "key": "...",
                "AWSAccessKeyId": "...",
                "policy": "...",
                "signature": "...",
                "Content-Type": "..."
            }
        }

    Client (JavaScript) usage:
        const formData = new FormData();
        Object.entries(post_data.fields).forEach(([k, v]) => formData.append(k, v));
        formData.append("file", file);   // "file" must be last field
        await fetch(post_data.url, { method: "POST", body: formData });
    """
    _client = client or s3_client

    # ${filename} is interpolated by S3 to the uploaded filename.
    key = f"{key_prefix}/${{filename}}"

    conditions: List[Any] = [
        # Enforce max file size.
        ["content-length-range", 0, max_size_bytes],
        # Restrict content-type to the declared prefix.
        ["starts-with", "$Content-Type", content_type.split("/")[0] + "/"],
        # Exact content-type match (belt-and-suspenders).
        {"Content-Type": content_type},
    ]

    result: Dict[str, Any] = _client.generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=conditions,
        ExpiresIn=expires_in,
    )
    return result


# ==========================================================================
# 6. MULTIPART UPLOAD — LARGE FILES (> 5 GB)
# ==========================================================================

def initiate_multipart_upload(
    bucket: str,
    key: str,
    content_type: str,
    client: Optional[Any] = None,
) -> str:
    """
    Start a multipart upload session and return the UploadId.

    S3 splits files into numbered parts (each 5 MB – 5 GB).  Parts are
    uploaded independently (in parallel from the client) and assembled by S3
    on completion.

    Returns:
        upload_id: string token identifying this multipart session.
    """
    _client = client or s3_client
    response = _client.create_multipart_upload(
        Bucket=bucket,
        Key=key,
        ContentType=content_type,
    )
    upload_id: str = response["UploadId"]
    log.info("Initiated multipart upload: s3://%s/%s (upload_id=%s)", bucket, key, upload_id)
    return upload_id


def generate_part_upload_url(
    bucket: str,
    key: str,
    upload_id: str,
    part_number: int,
    expires_in: int = TTL_MULTIPART_PART,
    client: Optional[Any] = None,
) -> str:
    """
    Generate a presigned URL for uploading a single multipart part.

    ``part_number`` must be between 1 and 10 000 (S3 limit).
    The client receives the ETag from S3 in the response headers after PUT;
    it must collect all ETags for the complete_multipart_upload call.
    """
    _client = client or s3_client
    url: str = _client.generate_presigned_url(
        "upload_part",
        Params={
            "Bucket": bucket,
            "Key": key,
            "UploadId": upload_id,
            "PartNumber": part_number,
        },
        ExpiresIn=expires_in,
    )
    return url


def generate_all_part_urls(
    bucket: str,
    key: str,
    upload_id: str,
    total_parts: int,
    client: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Generate presigned URLs for all parts of a multipart upload in one call.

    Returns a list of dicts:
        [{"part_number": 1, "url": "https://...s3...?..."}, ...]

    The client uploads each part in parallel using these URLs, then sends
    the collected ETags back to the server to complete the upload.
    """
    return [
        {
            "part_number": i,
            "url": generate_part_upload_url(
                bucket=bucket,
                key=key,
                upload_id=upload_id,
                part_number=i,
                client=client,
            ),
        }
        for i in range(1, total_parts + 1)
    ]


def complete_multipart_upload(
    bucket: str,
    key: str,
    upload_id: str,
    parts: List[Dict[str, Any]],
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Assemble multipart parts into the final S3 object.

    ``parts`` must be sorted by PartNumber and each entry must include the
    ETag returned by S3 after each part PUT:
        [{"PartNumber": 1, "ETag": '"abc123"'}, ...]

    Theory: ETags include surrounding double-quotes — preserve them verbatim.
    """
    _client = client or s3_client
    response = _client.complete_multipart_upload(
        Bucket=bucket,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": sorted(parts, key=lambda p: p["PartNumber"])},
    )
    log.info("Completed multipart upload: s3://%s/%s", bucket, key)
    return response


def abort_multipart_upload(
    bucket: str,
    key: str,
    upload_id: str,
    client: Optional[Any] = None,
) -> None:
    """
    Cancel an in-progress multipart upload and free partial storage.

    Theory §Common Pitfalls #4:
        Incomplete multipart uploads leave partial objects in storage and
        S3 charges for them.  Always abort on failure.  Additionally, set
        a bucket lifecycle rule (see LIFECYCLE_RULE_ABORT_MULTIPART below)
        to auto-clean orphans after a time window.
    """
    _client = client or s3_client
    _client.abort_multipart_upload(
        Bucket=bucket,
        Key=key,
        UploadId=upload_id,
    )
    log.warning("Aborted multipart upload: s3://%s/%s (upload_id=%s)", bucket, key, upload_id)


# Lifecycle rule JSON to attach at bucket level — auto-aborts orphan uploads.
LIFECYCLE_RULE_ABORT_MULTIPART: Dict[str, Any] = {
    "Rules": [{
        "ID": "abort-incomplete-multipart",
        "Status": "Enabled",
        "Filter": {"Prefix": ""},          # applies to all prefixes
        "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
    }]
}


# ==========================================================================
# 7. FASTAPI INTEGRATION — INIT + COMPLETE ENDPOINTS
# ==========================================================================

# pip install fastapi pydantic
try:
    from fastapi import Depends, FastAPI, HTTPException  # type: ignore
    from pydantic import BaseModel, Field               # type: ignore
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

if _FASTAPI_AVAILABLE:

    app = FastAPI(title="File Upload Service")

    # ------------------------------------------------------------------
    # Request / response schemas
    # ------------------------------------------------------------------

    class UploadInitRequest(BaseModel):
        filename: str = Field(..., description="Original filename from the client")
        content_type: str = Field(..., description="MIME type, e.g. image/jpeg")
        size_bytes: int = Field(..., gt=0, description="Declared file size")

    class UploadInitResponse(BaseModel):
        file_id: str
        upload_url: str
        key: str
        expires_in: int

    class UploadCompleteRequest(BaseModel):
        file_id: str

    # ------------------------------------------------------------------
    # Dependency stubs (replace with real auth + DB in production)
    # ------------------------------------------------------------------

    def get_current_user() -> Dict[str, str]:
        """Stub: returns a fake authenticated user."""
        return {"id": "user-123", "email": "user@example.com"}

    BUCKET = "my-app-bucket"

    # ------------------------------------------------------------------
    # POST /files/upload-url — issue a presigned PUT URL
    # ------------------------------------------------------------------

    @app.post("/files/upload-url", response_model=UploadInitResponse)
    async def init_upload(
        req: UploadInitRequest,
        user: Dict[str, str] = Depends(get_current_user),
    ) -> UploadInitResponse:
        """
        Step 1 of direct-upload flow.

        Validates the request, generates a short-lived presigned PUT URL,
        inserts a pending DB record, and returns the URL to the client.

        The client then PUTs the file directly to S3 — the API server never
        touches the file bytes.

        Security checks (theory §Security):
          - Size guard: reject before issuing URL.
          - Content-type guard: restrict to known safe types.
          - URL TTL: 15 minutes (TTL_UPLOAD constant).
        """
        # Guard: size
        if req.size_bytes > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum size of {MAX_UPLOAD_BYTES} bytes",
            )

        # Guard: content-type
        if req.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported content type: {req.content_type}",
            )

        key = build_user_object_key(user["id"], req.filename)
        file_id = str(uuid.uuid4())

        # In production: persist pending record to DB here.
        # await db.execute(
        #     "INSERT INTO files (id, user_id, key, status) VALUES ($1, $2, $3, 'pending')",
        #     file_id, user["id"], key
        # )

        upload_url = generate_upload_url(
            bucket=BUCKET,
            key=key,
            content_type=req.content_type,
            expires_in=TTL_UPLOAD,
        )

        return UploadInitResponse(
            file_id=file_id,
            upload_url=upload_url,
            key=key,
            expires_in=TTL_UPLOAD,
        )

    # ------------------------------------------------------------------
    # POST /files/{file_id}/complete — verify object exists, mark uploaded
    # ------------------------------------------------------------------

    @app.post("/files/{file_id}/complete")
    async def complete_upload(
        file_id: str,
        user: Dict[str, str] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        """
        Step 3 of direct-upload flow (step 2 is client PUT to S3).

        After the client has PUT the file to S3 it calls this endpoint.
        The server verifies the object actually exists via head_object and
        then marks the DB record as 'uploaded'.

        head_object verifies the upload without downloading the bytes —
        cheap and fast.
        """
        # In production: fetch file record from DB and verify ownership.
        # file = await db.fetch_one("SELECT * FROM files WHERE id = $1", file_id)
        # if file is None or file.user_id != user["id"]:
        #     raise HTTPException(403)
        key = f"users/{user['id']}/placeholder-{file_id}"

        if s3_client is not None:
            try:
                head = s3_client.head_object(Bucket=BUCKET, Key=key)
                size = head["ContentLength"]
            except ClientError as exc:
                error_code = exc.response["Error"]["Code"]  # type: ignore[attr-defined]
                if error_code in ("404", "NoSuchKey"):
                    raise HTTPException(
                        status_code=400,
                        detail="File not found in S3 — upload may have failed",
                    )
                raise

            # In production: update DB record here.
            # await db.execute(
            #     "UPDATE files SET status='uploaded', size_bytes=$1 WHERE id=$2",
            #     size, file_id
            # )
            log.info("Upload complete: file_id=%s size=%d", file_id, size)

        return {"status": "complete", "file_id": file_id}

    # ------------------------------------------------------------------
    # GET /files/{file_id}/download-url — issue short-lived GET URL
    # ------------------------------------------------------------------

    @app.get("/files/{file_id}/download-url")
    async def get_download_url_endpoint(
        file_id: str,
        user: Dict[str, str] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        """
        Generate a presigned GET URL for downloading a file.

        Theory §Why Presigned URLs:
            The response is ~200 bytes (the URL).  All subsequent bandwidth
            goes directly between the client and S3.
        """
        # In production: look up key and verify ownership from DB.
        key = f"users/{user['id']}/placeholder-{file_id}"

        url = generate_download_url(
            bucket=BUCKET,
            key=key,
            expires_in=TTL_DOWNLOAD,
            filename_override="download.bin",
        )
        return {"download_url": url, "expires_in": TTL_DOWNLOAD}

    # ------------------------------------------------------------------
    # POST /files/multipart/init — begin large-file upload
    # ------------------------------------------------------------------

    class MultipartInitRequest(BaseModel):
        filename: str
        content_type: str
        total_parts: int = Field(..., ge=1, le=10_000)

    @app.post("/files/multipart/init")
    async def init_multipart(
        req: MultipartInitRequest,
        user: Dict[str, str] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        """
        Initiate a multipart upload session and return presigned URLs for all
        parts.

        The client:
          1. Calls this endpoint → receives upload_id + list of part URLs.
          2. PUTs each part to its URL in parallel, collecting ETags.
          3. Calls /files/multipart/complete with the ETags.

        Use this endpoint for files larger than 5 GB (S3's single-PUT limit).
        Recommend part size of 50–100 MB for parallelism efficiency.
        """
        key = build_user_object_key(user["id"], req.filename)

        if s3_client is not None:
            upload_id = initiate_multipart_upload(
                bucket=BUCKET,
                key=key,
                content_type=req.content_type,
            )
            part_urls = generate_all_part_urls(
                bucket=BUCKET,
                key=key,
                upload_id=upload_id,
                total_parts=req.total_parts,
            )
        else:
            upload_id = "stub-upload-id"
            part_urls = [
                {"part_number": i, "url": f"https://stub.s3.example.com/part/{i}"}
                for i in range(1, req.total_parts + 1)
            ]

        return {
            "upload_id": upload_id,
            "key": key,
            "part_urls": part_urls,
        }

    class MultipartCompleteRequest(BaseModel):
        key: str
        upload_id: str
        parts: List[Dict[str, Any]]  # [{"PartNumber": 1, "ETag": "..."}, ...]

    @app.post("/files/multipart/complete")
    async def complete_multipart(
        req: MultipartCompleteRequest,
        user: Dict[str, str] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        """
        Assemble the multipart upload from collected part ETags.

        Theory §Direct Multipart Upload:
            S3 requires parts to be ≥ 5 MB except the last.
            ETags are returned by S3 after each part PUT (in response headers).
        """
        if s3_client is not None:
            complete_multipart_upload(
                bucket=BUCKET,
                key=req.key,
                upload_id=req.upload_id,
                parts=req.parts,
            )

        return {"status": "assembled", "key": req.key}


# ==========================================================================
# 8. CLOUDFRONT SIGNED URL — CDN LAYER
# ==========================================================================

# pip install cryptography
try:
    from botocore.signers import CloudFrontSigner  # type: ignore
    _CF_AVAILABLE = True
except ImportError:
    _CF_AVAILABLE = False


def _rsa_signer(message: bytes, private_key_pem: bytes) -> bytes:
    """
    RSA-SHA1 signer required by CloudFrontSigner.

    ``private_key_pem`` is the PEM-encoded RSA private key associated with
    the CloudFront key pair whose ID is passed to generate_cloudfront_url().

    pip install cryptography
    """
    try:
        from cryptography.hazmat.backends import default_backend    # type: ignore
        from cryptography.hazmat.primitives import hashes, serialization  # type: ignore
        from cryptography.hazmat.primitives.asymmetric import padding  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pip install cryptography") from exc

    private_key = serialization.load_pem_private_key(
        private_key_pem, password=None, backend=default_backend()
    )
    return private_key.sign(message, padding.PKCS1v15(), hashes.SHA1())  # noqa: S303


def generate_cloudfront_url(
    cf_base_url: str,
    object_path: str,
    key_id: str,
    private_key_pem: bytes,
    expires_in: int = TTL_DOWNLOAD,
) -> str:
    """
    Sign a CloudFront URL so private S3 content is served via CDN.

    Architecture (theory §CloudFront / CDN):
        Browser → CloudFront edge → cached? → return
                                   → miss  → S3 → cache → return

    Benefits vs. direct S3 presigned:
        - Lower latency (edge closer to user).
        - Cheaper bandwidth ($0.085/GB vs $0.09/GB).
        - HTTPS termination + DDoS protection + custom domain.
        - Signed cookies available for batch access to many objects.

    ``cf_base_url``   CloudFront distribution URL, e.g. https://d1234.cloudfront.net
    ``object_path``   Path relative to distribution root, e.g. /users/123/avatar.jpg
    ``key_id``        CloudFront key-pair ID from AWS console.
    ``private_key_pem`` PEM bytes of the corresponding RSA private key.
    """
    if not _CF_AVAILABLE:
        raise RuntimeError("botocore.signers.CloudFrontSigner not available — pip install boto3")

    signer = CloudFrontSigner(key_id, lambda msg: _rsa_signer(msg, private_key_pem))
    expire_date = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
        seconds=expires_in
    )
    full_url = cf_base_url.rstrip("/") + "/" + object_path.lstrip("/")
    return signer.generate_presigned_url(full_url, date_less_than=expire_date)


# ==========================================================================
# 9. ENCRYPTION AT REST
# ==========================================================================

def put_object_encrypted(
    bucket: str,
    key: str,
    body: bytes,
    encryption: str = "AES256",
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Upload an object with explicit server-side encryption.

    Theory §Best Practices — Encryption at rest:
        "AES256" → S3-managed keys (SSE-S3).   Free, no extra latency.
        "aws:kms" → KMS-managed keys (SSE-KMS). Audit trail, key rotation.

    Default encryption at bucket level eliminates the need to specify this
    per-object, but explicit specification adds a defence-in-depth layer.
    """
    _client = client or s3_client
    return _client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ServerSideEncryption=encryption,
    )


# ==========================================================================
# 10. UTILITY — CONTENT-TYPE VALIDATION
# ==========================================================================

def validate_content_type(
    declared_content_type: str,
    allowed_types: Optional[List[str]] = None,
) -> None:
    """
    Raise ValueError if ``declared_content_type`` is not in the allowed set.

    Call this server-side before generating any presigned URL.

    Theory §Common Pitfalls #6:
        "Client uploads jpg but says content_type=image/png → confused browsers."
    Theory §Security — Validate Content-Type at S3:
        "Use presigned POST conditions to restrict file types."

    Even with S3-side conditions you should validate early to return a
    meaningful error to the caller before spending the AWS API call budget.
    """
    allowed = allowed_types or ALLOWED_IMAGE_TYPES
    if declared_content_type not in allowed:
        raise ValueError(
            f"Content type '{declared_content_type}' is not permitted. "
            f"Allowed: {allowed}"
        )


def assert_sse_header_required(params: Dict[str, Any]) -> None:
    """
    Warn when a PUT URL includes SSE but the caller may forget the header.

    Theory §Common Pitfalls #1:
        If bucket policy requires SSE, the signed PUT URL must embed the
        encryption header AND the client must echo it back verbatim.
        Forgetting it yields a 403 that is hard to debug.

    This is a development-time guard — call it after building params.
    """
    sse = params.get("ServerSideEncryption")
    if sse:
        log.warning(
            "SSE '%s' included in presigned PUT params. "
            "Client MUST send the header: x-amz-server-side-encryption: %s",
            sse, sse,
        )


# ==========================================================================
# 11. REFERENCE — BUCKET POLICY SNIPPETS
# ==========================================================================

# Block public ACLs and grant access only via presigned URLs / CloudFront.
# Apply via console or terraform aws_s3_bucket_public_access_block.
BUCKET_BLOCK_PUBLIC_ACCESS: Dict[str, bool] = {
    "BlockPublicAcls": True,
    "IgnorePublicAcls": True,
    "BlockPublicPolicy": True,
    "RestrictPublicBuckets": True,
}

# Deny PutObject unless the request comes with the required SSE tag.
# (Illustrative JSON — apply via S3 bucket policy resource.)
BUCKET_POLICY_REQUIRE_SSE: str = """{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Deny",
    "Principal": "*",
    "Action": "s3:PutObject",
    "Resource": "arn:aws:s3:::my-bucket/*",
    "Condition": {
      "StringNotEquals": {
        "s3:x-amz-server-side-encryption": "AES256"
      }
    }
  }]
}"""

# Lifecycle rule: move objects to cheaper storage tiers over time.
# theory §Best Practices — Lifecycle rules
LIFECYCLE_RULE_TIERED_STORAGE: Dict[str, Any] = {
    "Rules": [{
        "ID": "tier-cold-data",
        "Status": "Enabled",
        "Filter": {"Prefix": "logs/"},
        "Transitions": [
            {"Days": 30, "StorageClass": "STANDARD_IA"},
            {"Days": 90, "StorageClass": "GLACIER"},
        ],
        "Expiration": {"Days": 365},
    }]
}


# ==========================================================================
# 12. KEY DESIGN DECISION REFERENCE (non-executable documentation)
# ==========================================================================

_DESIGN_NOTES: str = """
Direct-upload flow (three steps):
  1. Client → POST /files/upload-url   → API returns presigned PUT URL
  2. Client → PUT <presigned URL>      → Client uploads bytes straight to S3
  3. Client → POST /files/{id}/complete → API verifies via head_object; marks DB

Why three steps?
  Step 3 is essential.  Without it, your DB record stays "pending" forever
  if the client silently drops after step 2.  head_object is a cheap verify.

Object key pattern:
  users/<user_id>/<uuid>-<filename>
  - user_id prefix → natural IAM policy scope.
  - uuid prefix   → avoids hot-partition on sequential filenames.
  - filename      → human-readable, lowercase, hyphenated.

S3 storage cost reference:
  Standard       $0.023 / GB / month  — hot data
  Standard-IA    $0.0125 / GB         — infrequent (>30-day min)
  Glacier        $0.0036 / GB         — archive (retrieval in minutes)
  Glacier Deep   $0.00099 / GB        — long-term (retrieval in hours)

Transfer cost:
  Upload to S3:         FREE
  S3 → internet:        $0.09 / GB
  S3 → CloudFront:      cheaper; CloudFront → internet $0.085 / GB
  → Always front high-volume serving with CloudFront.
"""
