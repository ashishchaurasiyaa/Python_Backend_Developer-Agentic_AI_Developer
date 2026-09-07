"""Lab 4 -- Secrets Manager versioning: AWSCURRENT vs AWSPREVIOUS.

The scenario: rotating a secret (e.g. a DB password) doesn't delete the old
value immediately -- Secrets Manager keeps the previous version tagged
AWSPREVIOUS and the new one tagged AWSCURRENT. This matters during the
rotation WINDOW: any process that already has a connection open, or reads
the secret a split-second before your app finishes rolling out, still needs
the OLD value to keep working until it can pick up the new one -- that's
exactly what AWSPREVIOUS is for.

TODO lab: `get_secret()` below ALWAYS fetches whatever's tagged
AWSCURRENT, no matter what stage you ask it for -- it silently ignores the
`stage` argument entirely. Code written against this function can never
actually retrieve the previous value during a rotation window.

YOUR TASK: pass the `stage` argument through to the actual API call, via
the VersionStage parameter:

    resp = client.get_secret_value(SecretId=secret_id, VersionStage=stage)
    return resp["SecretString"]
"""

import os

import boto3

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
SECRET_ID = "lab4/db-password"


def client():
    return boto3.client(
        "secretsmanager",
        endpoint_url=ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def create_and_rotate(sm) -> None:
    sm.create_secret(Name=SECRET_ID, SecretString="password-v1")
    print(f"created {SECRET_ID} = 'password-v1' (this becomes AWSCURRENT)")

    # A "rotation": put a new value. Secrets Manager automatically demotes
    # the PREVIOUS AWSCURRENT to AWSPREVIOUS and promotes this new one.
    sm.put_secret_value(SecretId=SECRET_ID, SecretString="password-v2")
    print("rotated to 'password-v2' -- this is now AWSCURRENT, 'password-v1' is now AWSPREVIOUS")


def get_secret(client_, secret_id: str, stage: str) -> str:
    """Fetch the secret value at a specific version stage
    (AWSCURRENT or AWSPREVIOUS)."""
    resp = client_.get_secret_value(SecretId=secret_id)
    return resp["SecretString"]
    # TODO: pass `stage` through as VersionStage=stage (see module docstring)


if __name__ == "__main__":
    sm = client()
    create_and_rotate(sm)

    current = get_secret(sm, SECRET_ID, stage="AWSCURRENT")
    previous = get_secret(sm, SECRET_ID, stage="AWSPREVIOUS")

    print(f"\nrequested AWSCURRENT  -> got {current!r} (expected 'password-v2')")
    print(f"requested AWSPREVIOUS -> got {previous!r} (expected 'password-v1')")
