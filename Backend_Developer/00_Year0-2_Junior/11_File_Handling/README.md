# 📁 File Handling

> **5 theory + 5 practical (1:1).** Har real backend me file upload/download aata hai —
> aur har interview me ek scenario question banta hai: *"user 500MB file upload kar raha hai, ab kya?"*

---

## 📚 Files

| # | Theory | Practical | Kya |
|---|---|---|---|
| 01 | [File uploads + streaming](01_file_uploads_streaming.md) | [`01_...py`](practical/01_file_uploads_streaming.py) | Streaming upload, chunking, size limits, temp files, MIME validation |
| 02 | [S3 presigned URLs](02_s3_presigned_urls.md) | [`02_...py`](practical/02_s3_presigned_urls.py) | Direct-to-S3 upload, presigned PUT/GET, expiry, CORS |
| 03 | [Image processing (Pillow)](03_image_processing_pillow.md) | [`03_...py`](practical/03_image_processing_pillow.py) | Resize, thumbnails, EXIF strip, format conversion |
| 04 | [PDF + Excel generation](04_pdf_excel_generation.md) | [`04_...py`](practical/04_pdf_excel_generation.py) | Invoice/report banana — reportlab, openpyxl **write** |
| 05 | [Pandas tabular data](05_pandas_tabular_backend.md) | [`05_...py`](practical/05_pandas_tabular_backend.py) | Messy CSV/Excel **read** + validate + bulk-insert, chunking, polars |

---

## 🎯 Scenario question ka jawab (interview me yahi poocha jata hai)

> *"User 500MB Excel upload karta hai — tumhara endpoint kya karega?"*

1. **Request me process mat karo** — 202 Accepted + job id, background worker (Celery) me daalo → [Celery](../../01_Year3-4_Mid/09_Celery/)
2. **Direct-to-S3** presigned URL — file tumhare server se guzre hi nahi ([02](02_s3_presigned_urls.md))
3. **Chunked read** — `pd.read_csv(chunksize=...)`, poori file memory me mat lo ([05](05_pandas_tabular_backend.md))
4. **Row-level validation** — 5000 errors ek saath mat batao, structured error report do ([05](05_pandas_tabular_backend.md))
5. **Bulk insert batching** — `bulk_create(batch_size=1000)`, ek-ek insert nahi

**Related:** [Celery (background jobs)](../../01_Year3-4_Mid/09_Celery/) · [FastAPI](../06_FastAPI/) · [Email/Notifications](../12_Email_Notifications/) · [AWS S3](../../../DevOps/07_Cloud_AWS/)
