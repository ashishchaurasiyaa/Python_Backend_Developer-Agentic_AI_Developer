"""Lab 3 -- DynamoDB conditional writes prevent lost updates.

The scenario: two "readers" (A and B) both GET the same account at
balance=100, version=1, into their own local variables -- this is the
realistic case where a lost update actually happens: the new value is
computed CLIENT-SIDE from a value that might already be stale by the time
the write goes out, not via DynamoDB's own atomic `SET x = x + :delta`
(which is safe on its own -- the bug only shows up when the increment
happens in application code instead).

A computes 100+50=150 and writes 150. B, using its OWN stale read of 100,
computes 100+30=130 and writes 130 -- silently overwriting A's change.
Final balance ends up 130, not 180. Nothing errors. This is what makes lost
updates dangerous: no exception, no log line, just quietly wrong data.

TODO lab: `apply_delta()` below does a plain, unconditional overwrite of
whatever the caller computed -- exactly the buggy pattern above.

YOUR TASK: add a ConditionExpression checking the version hasn't moved since
this caller did its own GET, and increment version as part of the same
write, so a stale writer's update is REJECTED instead of silently applied:

    table.update_item(
        Key={"account_id": account_id},
        UpdateExpression="SET balance = :new_balance, version = version + :one",
        ConditionExpression="version = :expected_version",
        ExpressionAttributeValues={
            ":new_balance": new_balance,
            ":one": 1,
            ":expected_version": expected_version,
        },
    )

(delete the old plain update_item call -- this replaces it entirely)
"""

import os

import boto3
from botocore.exceptions import ClientError

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
TABLE_NAME = "lab3-accounts"


def resource():
    return boto3.resource(
        "dynamodb",
        endpoint_url=ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def create_table(dynamodb):
    dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "account_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "account_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table = dynamodb.Table(TABLE_NAME)
    table.wait_until_exists()
    table.put_item(Item={"account_id": "acc1", "balance": 100, "version": 1})
    return table


def apply_delta(table, account_id: str, new_balance: int, expected_version: int) -> None:
    """Overwrite the account's balance with a value the CALLER already
    computed client-side (old_balance + delta) from its own earlier read."""
    table.update_item(
        Key={"account_id": account_id},
        UpdateExpression="SET balance = :new_balance",
        ExpressionAttributeValues={":new_balance": new_balance},
    )
    # TODO: replace the plain update_item call above with the conditional
    # version described in the module docstring


if __name__ == "__main__":
    dynamodb = resource()
    table = create_table(dynamodb)

    # Both A and B GET the SAME starting state: balance=100, version=1,
    # into their own local variables, before either one writes anything.
    a_read_balance, a_read_version = 100, 1
    b_read_balance, b_read_version = 100, 1
    print(f"A reads: balance={a_read_balance}, version={a_read_version} (wants to add 50)")
    print(f"B reads: balance={b_read_balance}, version={b_read_version} (wants to add 30)")

    print("\nA computes 100+50=150 client-side, writes it...")
    apply_delta(table, "acc1", new_balance=a_read_balance + 50, expected_version=a_read_version)
    a_state = table.get_item(Key={"account_id": "acc1"})["Item"]
    print(f"  after A: balance={a_state['balance']}, version={a_state['version']}")

    print("\nB computes 100+30=130 client-side from its STALE read, writes it...")
    try:
        apply_delta(table, "acc1", new_balance=b_read_balance + 30, expected_version=b_read_version)
        print("  B's write went through")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            print("  B's write was REJECTED (ConditionalCheckFailedException) -- correctly, its read was stale")
        else:
            raise

    final = table.get_item(Key={"account_id": "acc1"})["Item"]
    print(f"\nfinal state: balance={final['balance']}, version={final['version']}")
    print("expected if BOTH deltas had been safely applied: balance=180")
