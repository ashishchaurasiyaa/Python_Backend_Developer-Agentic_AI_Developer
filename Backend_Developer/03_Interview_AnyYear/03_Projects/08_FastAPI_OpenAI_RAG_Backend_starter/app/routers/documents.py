"""
Document ingestion endpoints (stubs — implemented Week 1 D4-D6).

Flow reference is kept in the docstrings/TODOs so the build order stays visible.
"""

from fastapi import APIRouter, File, UploadFile

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document for ingestion. MVP scope: PDF, MD.

    Flow (Week 1 D4-D6):
      1. get_current_tenant() from JWT / API-key header  (Day 2)
      2. validate MIME type + size vs tenant quota
      3. compute content_hash (SHA-256) to skip duplicate re-ingestion
      4. store raw file (local disk MVP; S3 later), insert documents row (status='processing')
      5. enqueue ingestion (BackgroundTasks/Celery — NOT Kafka in MVP)
      6. return { document_id, status: 'processing' }
    """
    return {
        "document_id": "TODO",
        "filename": file.filename,
        "status": "processing",
        "detail": "TODO: ingestion pipeline lands Week 1 D4-D6",
    }


@router.get("")
async def list_documents():
    # TODO(Day 2): tenant-scoped query on documents table
    return {"items": [], "detail": "TODO"}


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    # TODO: soft-delete document row; background task removes chunks from pgvector
    return {"detail": "TODO", "document_id": doc_id}
