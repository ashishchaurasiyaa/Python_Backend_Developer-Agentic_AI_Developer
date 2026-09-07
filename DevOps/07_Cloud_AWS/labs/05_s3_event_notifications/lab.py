"""Lab 5 -- S3 event notifications -> SQS.

The scenario: this is the entry point of almost every serverless/event-
driven pipeline built on S3 -- a file lands in a bucket, and something
downstream needs to react (process an upload, trigger a thumbnail job,
kick off an ETL step) WITHOUT polling the bucket. S3 can push a
notification straight to an SQS queue the instant an object is created.

TODO lab: the bucket below has NO notification configuration at all --
uploading a file to it is completely silent as far as anything downstream
is concerned.

YOUR TASK: configure the bucket to send an event to the queue on every
object creation:

    s3.put_bucket_notification_configuration(
        Bucket=bucket_name,
        NotificationConfiguration={
            "QueueConfigurations": [
                {
                    "QueueArn": queue_arn,
                    "Events": ["s3:ObjectCreated:*"],
                }
            ]
        },
    )
"""

import json
import os
import time

import boto3

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
BUCKET_NAME = "lab5-bucket"
QUEUE_NAME = "lab5-queue"


def clients():
    kwargs = dict(
        endpoint_url=ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    return boto3.client("s3", **kwargs), boto3.client("sqs", **kwargs)


def setup(s3, sqs) -> tuple[str, str]:
    s3.create_bucket(Bucket=BUCKET_NAME)

    queue_url = sqs.create_queue(QueueName=QUEUE_NAME)["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]

    # Let the bucket send to the queue (S3 -> SQS requires the queue's
    # access policy to allow it, even on LocalStack).
    bucket_arn = f"arn:aws:s3:::{BUCKET_NAME}"
    sqs.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={
            "Policy": json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": "sqs:SendMessage",
                            "Resource": queue_arn,
                            "Condition": {"ArnLike": {"aws:SourceArn": bucket_arn}},
                        }
                    ],
                }
            )
        },
    )

    return queue_url, queue_arn


def configure_notifications(s3, bucket_name: str, queue_arn: str) -> None:
    pass
    # TODO: call s3.put_bucket_notification_configuration (see the module
    # docstring for the exact call)


if __name__ == "__main__":
    s3, sqs = clients()
    queue_url, queue_arn = setup(s3, sqs)
    configure_notifications(s3, BUCKET_NAME, queue_arn)

    print(f"uploading an object to s3://{BUCKET_NAME}/hello.txt ...")
    s3.put_object(Bucket=BUCKET_NAME, Key="hello.txt", Body=b"hello from lab 5")

    time.sleep(2)  # give LocalStack a moment to deliver the event
    resp = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=2)
    messages = resp.get("Messages", [])
    print(f"\ntotal messages in the queue: {len(messages)}")

    object_created_events = 0
    for m in messages:
        body = json.loads(m["Body"])
        if body.get("Event") == "s3:TestEvent":
            # S3 sends this ONE test message the instant a notification
            # configuration is created, before any real object event --
            # a real AWS behavior, not a LocalStack quirk. Don't mistake it
            # for your actual upload event.
            print("  - s3:TestEvent (sent automatically when notifications were configured, not a real upload)")
            continue
        for record in body.get("Records", []):
            print(f"  - event: {record.get('eventName')}, key: {record['s3']['object']['key']}")
            if record.get("eventName", "").startswith("ObjectCreated"):
                object_created_events += 1

    print(f"\nreal ObjectCreated events received: {object_created_events}")
