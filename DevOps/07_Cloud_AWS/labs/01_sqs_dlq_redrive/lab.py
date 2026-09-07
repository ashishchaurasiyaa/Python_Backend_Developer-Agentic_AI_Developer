"""Lab 1 -- SQS visibility timeout + dead-letter queue (DLQ) redrive.

The scenario: a message repeatedly fails processing (a poison message --
malformed data, a downstream bug, whatever). Without a DLQ, SQS just keeps
redelivering it forever, once its visibility timeout expires each time --
a broken message can loop through your consumer indefinitely, drowning out
real work. A redrive policy with maxReceiveCount moves it to a separate
DLQ after N failed attempts, so it stops competing with real messages and
becomes something you inspect and fix deliberately.

TODO lab: `create_main_queue()` below creates the main queue with NO
redrive policy at all -- a message that keeps failing will loop forever.

YOUR TASK: add a RedrivePolicy so the queue moves a message to the DLQ
after maxReceiveCount=3 failed receive attempts:

    redrive_policy = {
        "deadLetterTargetArn": dlq_arn,
        "maxReceiveCount": "3",
    }
    sqs.set_queue_attributes(
        QueueUrl=main_queue_url,
        Attributes={"RedrivePolicy": json.dumps(redrive_policy)},
    )
"""

import json
import os
import time

import boto3

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")


def client():
    return boto3.client(
        "sqs",
        endpoint_url=ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def create_dlq(sqs) -> tuple[str, str]:
    resp = sqs.create_queue(QueueName="lab1-dlq")
    dlq_url = resp["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]
    return dlq_url, dlq_arn


def create_main_queue(sqs, dlq_arn: str) -> str:
    resp = sqs.create_queue(
        QueueName="lab1-main",
        Attributes={"VisibilityTimeout": "2"},  # short, so the lab runs fast
    )
    main_queue_url = resp["QueueUrl"]

    # TODO: set a RedrivePolicy on main_queue_url pointing at dlq_arn with
    # maxReceiveCount=3 (see the module docstring for the exact call)

    return main_queue_url


def simulate_poison_message(sqs, main_queue_url: str) -> None:
    """Send one message and receive-without-deleting it repeatedly,
    simulating a consumer that keeps failing to process it."""
    sqs.send_message(QueueUrl=main_queue_url, MessageBody="poison pill")

    for attempt in range(1, 6):
        resp = sqs.receive_message(
            QueueUrl=main_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=1
        )
        messages = resp.get("Messages", [])
        if messages:
            print(f"  attempt {attempt}: received message, NOT deleting it (simulated failure)")
        else:
            print(f"  attempt {attempt}: no message available in main queue right now")
        time.sleep(2.2)  # wait out the 2s VisibilityTimeout before the next attempt


if __name__ == "__main__":
    sqs = client()
    dlq_url, dlq_arn = create_dlq(sqs)
    main_queue_url = create_main_queue(sqs, dlq_arn)
    print(f"main queue: {main_queue_url}")
    print(f"dlq:        {dlq_url}")

    simulate_poison_message(sqs, main_queue_url)

    dlq_count = sqs.get_queue_attributes(
        QueueUrl=dlq_url, AttributeNames=["ApproximateNumberOfMessages"]
    )["Attributes"]["ApproximateNumberOfMessages"]
    print(f"messages now sitting in the DLQ: {dlq_count}")
