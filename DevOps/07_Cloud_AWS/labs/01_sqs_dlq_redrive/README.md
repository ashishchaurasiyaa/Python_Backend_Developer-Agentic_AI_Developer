# Lab 1 — SQS dead-letter queue redrive

**Goal:** Prove, live, that without a dead-letter queue (DLQ), a message
your consumer keeps failing to process loops through the main queue
**forever** — its visibility timeout expires, it becomes visible again,
gets received again, fails again, repeat indefinitely. A `RedrivePolicy`
with `maxReceiveCount` moves it to a separate DLQ after N failures, so it
stops competing with real messages.

> **Setup (once):** `(cd ../_setup && docker compose up -d)` — starts
> LocalStack with SQS/SNS/DynamoDB/Secrets Manager/S3.

**Task:** Open `lab.py`. `create_main_queue()` creates the main queue with
no redrive policy at all. Add one pointing at the DLQ with
`maxReceiveCount=3`:
```python
redrive_policy = {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "3"}
sqs.set_queue_attributes(
    QueueUrl=main_queue_url,
    Attributes={"RedrivePolicy": json.dumps(redrive_policy)},
)
```

**Verify:**
```bash
./verify.sh
```
Runs `lab.py` (which sends one message and receives-without-deleting it 5
times, simulating a consumer that keeps failing), then **independently**
checks the DLQ's message count via the AWS CLI — not just trusting
`lab.py`'s own printed output. PASS requires exactly 1 message in the DLQ.

**SOCH:**
- The unfilled stub's message keeps getting received 5 times and stays in
  the main queue the whole time — SQS is doing exactly what you told it to
  do. What's the actual mechanism (which SQS attribute) that makes a
  message "become visible again" after a failed receive, and why does that
  need to exist at all — what would break if a received message just
  vanished permanently the instant `receive_message` returned it?
- A message landing in the DLQ isn't itself a fix — it's evidence something
  is wrong. What would you actually DO with a message sitting in a DLQ in a
  real production incident, and why is "just increase maxReceiveCount so it
  stops happening" almost always the wrong response?
