"""Lab 2 -- SNS -> SQS fan-out with a message filter policy.

The scenario: a topic publishes every event (order created, updated,
cancelled...) but a particular queue only cares about `priority=urgent`
ones. Without a filter policy, every subscriber gets EVERY message and has
to filter client-side after paying to receive and process it. A
`FilterPolicy` on the SUBSCRIPTION does the filtering at the SNS layer --
the queue never even receives what it doesn't care about.

TODO lab: `subscribe_queue()` below subscribes the queue to the topic with
NO filter policy -- it will receive every message published, regardless of
its `priority` attribute.

YOUR TASK: add a FilterPolicy so the subscription only delivers messages
where the `priority` message attribute is "urgent":

    sns.set_subscription_attributes(
        SubscriptionArn=subscription_arn,
        AttributeName="FilterPolicy",
        AttributeValue=json.dumps({"priority": ["urgent"]}),
    )
"""

import json
import os
import time

import boto3

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")


def clients():
    kwargs = dict(
        endpoint_url=ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    return boto3.client("sns", **kwargs), boto3.client("sqs", **kwargs)


def setup(sns, sqs) -> tuple[str, str, str]:
    topic_arn = sns.create_topic(Name="lab2-topic")["TopicArn"]

    queue_url = sqs.create_queue(QueueName="lab2-queue")["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]

    # Let the topic send to the queue (SNS -> SQS requires the queue's
    # access policy to allow it, even on LocalStack).
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
                            "Condition": {"ArnEquals": {"aws:SourceArn": topic_arn}},
                        }
                    ],
                }
            )
        },
    )

    return topic_arn, queue_url, queue_arn


def subscribe_queue(sns, topic_arn: str, queue_arn: str) -> str:
    resp = sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)
    subscription_arn = resp["SubscriptionArn"]

    # TODO: add a FilterPolicy on this subscription (see the module
    # docstring for the exact call) so only priority=urgent messages
    # reach the queue

    return subscription_arn


def publish_messages(sns, topic_arn: str) -> None:
    messages = [
        ("order #1 created", "urgent"),
        ("order #2 created", "low"),
        ("order #3 created", "urgent"),
    ]
    for body, priority in messages:
        sns.publish(
            TopicArn=topic_arn,
            Message=body,
            MessageAttributes={"priority": {"DataType": "String", "StringValue": priority}},
        )
        print(f"  published: {body!r} (priority={priority})")


if __name__ == "__main__":
    sns, sqs = clients()
    topic_arn, queue_url, queue_arn = setup(sns, sqs)
    subscribe_queue(sns, topic_arn, queue_arn)

    publish_messages(sns, topic_arn)

    time.sleep(2)  # give LocalStack a moment to deliver
    resp = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=2)
    received = resp.get("Messages", [])
    print(f"\nmessages that reached the queue: {len(received)}")
    for m in received:
        body = json.loads(m["Body"])
        print(f"  - {body.get('Message')!r}")
