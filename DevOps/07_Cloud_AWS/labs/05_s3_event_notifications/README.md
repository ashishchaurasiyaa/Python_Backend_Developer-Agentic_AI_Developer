# Lab 5 — S3 event notifications → SQS

**Goal:** Prove, live, the entry point of almost every serverless
pipeline built on S3: a file lands in a bucket, and a queue gets a message
about it automatically — no polling, no cron job checking "did anything new
show up."

**Task:** Open `lab.py`. `configure_notifications()` is currently empty —
uploading to the bucket is completely silent as far as anything downstream
is concerned. Add:
```python
s3.put_bucket_notification_configuration(
    Bucket=bucket_name,
    NotificationConfiguration={
        "QueueConfigurations": [{"QueueArn": queue_arn, "Events": ["s3:ObjectCreated:*"]}]
    },
)
```

**Verify:**
```bash
./verify.sh
```
Runs `lab.py`, which uploads `hello.txt` to the bucket after configuring
notifications. PASS requires exactly 1 real `ObjectCreated` event reaches
the queue, correctly identifying `hello.txt` as the uploaded key.

> **A real discovery, worth knowing:** the first time this lab was built,
> the filled-in version showed **2** total messages in the queue, not 1 —
> which looked like a bug. It wasn't: S3 sends one `s3:TestEvent` message
> the instant a notification configuration is created, before any real
> upload happens, to verify the destination is reachable. This is genuine
> AWS behavior (not a LocalStack quirk) and `lab.py` now explicitly
> distinguishes it from real `ObjectCreated` events instead of just
> counting raw messages — check `verify.sh`'s reasoning for how.

**SOCH:**
- The `s3:TestEvent` fires once, at configuration time, regardless of
  whether any object is ever uploaded afterward. If your code just counted
  "did I get a message" as proof notifications work, what false confidence
  would that give you?
- This lab used `Events: ["s3:ObjectCreated:*"]` — every kind of creation
  (PUT, POST, multipart-complete, copy). What real difference would it make
  to instead scope it to `s3:ObjectCreated:Put` only, and when would that
  narrower scope actually matter for a downstream consumer?
