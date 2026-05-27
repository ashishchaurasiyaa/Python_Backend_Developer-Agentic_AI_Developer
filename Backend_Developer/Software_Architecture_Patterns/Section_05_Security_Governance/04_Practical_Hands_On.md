# Lecture 4 — Practical Hands-On: Secrets & Token Management

> **Theory file:** [04_Secrets_Token_Management.md](04_Secrets_Token_Management.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Production secrets management:

1. ✅ **HashiCorp Vault** local setup with KV + dynamic secrets
2. ✅ **AWS Secrets Manager** integration in Python
3. ✅ **Automatic rotation** with Lambda
4. ✅ **Dynamic DB credentials** via Vault
5. ✅ **K8s External Secrets** operator
6. ✅ **Refresh token rotation** with reuse detection
7. ✅ **Secret scanning** — pre-commit + CI
8. ✅ **Encryption** with envelope encryption
9. ✅ **Log scrubbing** for sensitive data
10. ✅ **Incident response** runbook

By end: aap **production-grade secrets management** ko implement kar sakte ho.

---

## 1. Project Structure

```
secrets_management_demo/
├── docker-compose.yml
├── README.md
│
├── vault/
│   ├── policies/
│   ├── secrets_engine.sh
│   ├── client.py
│   └── dynamic_db_creds.py
│
├── aws_secrets/
│   ├── manager.py
│   ├── rotation_lambda.py
│   └── caching.py
│
├── kubernetes/
│   ├── external-secrets.yaml
│   └── sealed-secrets.yaml
│
├── refresh_tokens/
│   ├── manager.py
│   ├── rotation.py
│   └── reuse_detection.py
│
├── encryption/
│   ├── envelope.py
│   └── field_encryption.py
│
├── leak_detection/
│   ├── pre_commit_config.yaml
│   ├── ci_workflow.yml
│   └── log_scrubber.py
│
└── incident_response/
    └── runbook.md
```

---

## 2. Setup & Dependencies

```bash
pip install hvac                        # HashiCorp Vault client
pip install boto3                       # AWS Secrets Manager
pip install azure-keyvault-secrets      # Azure
pip install cryptography
pip install python-jose
pip install detect-secrets              # Leak detection
```

---

## 3. 🔐 HashiCorp Vault Local Setup

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  vault:
    image: hashicorp/vault:latest
    ports:
      - "8200:8200"
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: dev-root-token
      VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
      VAULT_ADDR: http://0.0.0.0:8200
    cap_add:
      - IPC_LOCK
    volumes:
      - vault_data:/vault/file

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: admin_pass
      POSTGRES_DB: myapp
    ports:
      - "5432:5432"

volumes:
  vault_data:
```

### Initial Setup Script

```bash
#!/bin/bash
# setup_vault.sh

export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=dev-root-token

# Enable KV v2 secrets engine
vault secrets enable -version=2 kv

# Store some secrets
vault kv put kv/myapp/database \
    username=app_user \
    password=super_secret_password_123

vault kv put kv/myapp/api \
    stripe_key=sk_live_xxx \
    sendgrid_key=SG.xxx

# Create a policy
cat > app-policy.hcl <<EOF
path "kv/data/myapp/*" {
  capabilities = ["read"]
}
EOF

vault policy write app-policy app-policy.hcl

# Enable AppRole auth method
vault auth enable approle
vault write auth/approle/role/my-app \
    secret_id_ttl=24h \
    token_ttl=1h \
    token_max_ttl=4h \
    policies=app-policy

# Get role-id and secret-id
ROLE_ID=$(vault read -field=role_id auth/approle/role/my-app/role-id)
SECRET_ID=$(vault write -force -field=secret_id auth/approle/role/my-app/secret-id)

echo "ROLE_ID: $ROLE_ID"
echo "SECRET_ID: $SECRET_ID"
```

### `vault/client.py` — Python Client

```python
"""
HashiCorp Vault client for application.
"""
import hvac
import os
import time
from typing import Optional, Any

class VaultClient:
    """
    Application client that:
    - Authenticates via AppRole
    - Caches secrets locally
    - Renews token before expiry
    - Refetches secrets periodically
    """
    
    def __init__(self, vault_url: str, role_id: str, secret_id: str):
        self.client = hvac.Client(url=vault_url)
        self.role_id = role_id
        self.secret_id = secret_id
        self._token_expiry: Optional[float] = None
        self._secrets_cache: dict[str, dict] = {}
        self._cache_expiry: dict[str, float] = {}
    
    def _authenticate(self):
        """Authenticate using AppRole"""
        response = self.client.auth.approle.login(
            role_id=self.role_id,
            secret_id=self.secret_id,
        )
        self._token_expiry = time.time() + response['auth']['lease_duration'] - 60  # 1 min buffer
        print(f"[VAULT] Authenticated, token valid for {response['auth']['lease_duration']}s")
    
    def _ensure_authenticated(self):
        """Re-auth if token expired"""
        if not self._token_expiry or time.time() >= self._token_expiry:
            self._authenticate()
    
    def get_secret(self, path: str, cache_ttl: int = 300) -> dict:
        """
        Fetch secret from Vault with local caching.
        Cache TTL prevents hammering Vault.
        """
        # Check cache
        if path in self._secrets_cache:
            if time.time() < self._cache_expiry[path]:
                return self._secrets_cache[path]
        
        # Authenticate if needed
        self._ensure_authenticated()
        
        # Fetch from Vault
        response = self.client.secrets.kv.v2.read_secret_version(path=path)
        secret = response['data']['data']
        
        # Cache
        self._secrets_cache[path] = secret
        self._cache_expiry[path] = time.time() + cache_ttl
        
        print(f"[VAULT] Fetched {path}")
        return secret

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
vault = VaultClient(
    vault_url="http://localhost:8200",
    role_id=os.environ["VAULT_ROLE_ID"],
    secret_id=os.environ["VAULT_SECRET_ID"],
)

# At startup
db_creds = vault.get_secret("myapp/database")
api_keys = vault.get_secret("myapp/api")

# Connect to DB
db_url = f"postgresql://{db_creds['username']}:{db_creds['password']}@localhost/myapp"
```

---

## 4. 🔄 Dynamic Database Credentials

### Setup Dynamic Secrets Engine

```bash
# Enable database secrets engine
vault secrets enable database

# Configure PostgreSQL connection
vault write database/config/postgres \
    plugin_name=postgresql-database-plugin \
    connection_url="postgresql://{{username}}:{{password}}@postgres:5432/myapp?sslmode=disable" \
    allowed_roles="my-app-role" \
    username="admin" \
    password="admin_pass"

# Create role for app
vault write database/roles/my-app-role \
    db_name=postgres \
    creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
                          GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
    default_ttl="1h" \
    max_ttl="24h"
```

### `vault/dynamic_db_creds.py`

```python
"""
Use dynamic DB credentials from Vault.
Each app instance gets a UNIQUE, SHORT-LIVED credential.
"""
import hvac
import asyncpg
import asyncio
import time
from typing import Optional

class DynamicDBCredentials:
    """
    Fetches DB credentials on-demand from Vault.
    Credentials auto-expire (Vault revokes them).
    """
    
    def __init__(self, vault_client: hvac.Client):
        self.vault = vault_client
        self._username: Optional[str] = None
        self._password: Optional[str] = None
        self._lease_id: Optional[str] = None
        self._expires_at: Optional[float] = None
        self._pool: Optional[asyncpg.Pool] = None
    
    async def get_credentials(self) -> dict:
        """Get fresh credentials (or use cached if still valid)"""
        if self._expires_at and time.time() < self._expires_at - 300:  # 5 min buffer
            return {"username": self._username, "password": self._password}
        
        # Request new credentials
        response = self.vault.secrets.database.generate_credentials(name="my-app-role")
        
        self._username = response['data']['username']
        self._password = response['data']['password']
        self._lease_id = response['lease_id']
        self._expires_at = time.time() + response['lease_duration']
        
        print(f"[VAULT] New DB credentials: {self._username} (expires in {response['lease_duration']}s)")
        
        return {"username": self._username, "password": self._password}
    
    async def get_connection_pool(self) -> asyncpg.Pool:
        """Create connection pool with dynamic creds"""
        if self._pool and time.time() < self._expires_at - 600:
            return self._pool
        
        # Close old pool if exists
        if self._pool:
            await self._pool.close()
        
        # Get new credentials
        creds = await self.get_credentials()
        
        # Create new pool
        self._pool = await asyncpg.create_pool(
            host="postgres",
            user=creds["username"],
            password=creds["password"],
            database="myapp",
            min_size=5,
            max_size=20,
        )
        
        return self._pool

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
async def main():
    vault_client = hvac.Client(url="http://localhost:8200", token="...")
    
    db = DynamicDBCredentials(vault_client)
    pool = await db.get_connection_pool()
    
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT COUNT(*) FROM users")
        print(f"Users: {result}")
    
    # Each time you call get_credentials(), you may get a FRESH credential
    # Old ones auto-revoke!

asyncio.run(main())
```

---

## 5. ☁️ AWS Secrets Manager

### `aws_secrets/manager.py`

```python
"""
AWS Secrets Manager integration with caching.
"""
import boto3
import json
import time
from typing import Optional, Any

class AWSSecretsCache:
    """
    Cached AWS Secrets Manager client.
    Reduces API calls (cost + rate limits).
    """
    
    def __init__(self, region: str = "us-east-1"):
        self.client = boto3.client("secretsmanager", region_name=region)
        self._cache: dict[str, tuple[Any, float]] = {}
    
    def get_secret(
        self,
        secret_id: str,
        version_stage: str = "AWSCURRENT",
        cache_ttl: int = 300,  # 5 minutes
    ) -> dict:
        """Get secret with local caching"""
        cache_key = f"{secret_id}:{version_stage}"
        
        # Check cache
        if cache_key in self._cache:
            value, expiry = self._cache[cache_key]
            if time.time() < expiry:
                return value
        
        # Fetch from AWS
        response = self.client.get_secret_value(
            SecretId=secret_id,
            VersionStage=version_stage,
        )
        
        # Parse
        if "SecretString" in response:
            secret = json.loads(response["SecretString"])
        else:
            secret = response["SecretBinary"]
        
        # Cache
        self._cache[cache_key] = (secret, time.time() + cache_ttl)
        
        return secret
    
    def get_pending_secret(self, secret_id: str) -> Optional[dict]:
        """
        Get pending secret (during rotation).
        Used to test new credentials before they become current.
        """
        try:
            return self.get_secret(secret_id, version_stage="AWSPENDING")
        except self.client.exceptions.ResourceNotFoundException:
            return None

# ─────────────────────────────────────────────────────────────
# USAGE
# ─────────────────────────────────────────────────────────────
secrets = AWSSecretsCache(region="us-east-1")

# At app startup
db_secret = secrets.get_secret("prod/myapp/db")
print(f"DB host: {db_secret['host']}")

# Or fetch lazily
def get_stripe_key():
    return secrets.get_secret("prod/myapp/stripe")["api_key"]
```

### Automatic Rotation Lambda

```python
"""
Lambda function for rotating database password.
Called automatically by Secrets Manager on schedule.
"""
import boto3
import json
import psycopg2

secrets_client = boto3.client("secretsmanager")

def lambda_handler(event, context):
    """
    Rotation function called by Secrets Manager.
    
    Step 1: createSecret - create new password
    Step 2: setSecret - update DB with new password
    Step 3: testSecret - verify new password works
    Step 4: finishSecret - mark new password as AWSCURRENT
    """
    arn = event["SecretId"]
    token = event["ClientRequestToken"]
    step = event["Step"]
    
    if step == "createSecret":
        create_secret(arn, token)
    elif step == "setSecret":
        set_secret(arn, token)
    elif step == "testSecret":
        test_secret(arn, token)
    elif step == "finishSecret":
        finish_secret(arn, token)

def create_secret(arn, token):
    """Generate new password"""
    # Get current secret to know username
    current = secrets_client.get_secret_value(SecretId=arn, VersionStage="AWSCURRENT")
    current_dict = json.loads(current["SecretString"])
    
    # Generate new password
    new_password = secrets_client.get_random_password(
        PasswordLength=32,
        ExcludeCharacters='"@/\\'
    )
    
    # Save as AWSPENDING
    new_secret = {
        **current_dict,
        "password": new_password["RandomPassword"],
    }
    
    secrets_client.put_secret_value(
        SecretId=arn,
        ClientRequestToken=token,
        SecretString=json.dumps(new_secret),
        VersionStages=["AWSPENDING"]
    )

def set_secret(arn, token):
    """Update database with new password"""
    pending = secrets_client.get_secret_value(SecretId=arn, VersionStage="AWSPENDING")
    pending_dict = json.loads(pending["SecretString"])
    
    current = secrets_client.get_secret_value(SecretId=arn, VersionStage="AWSCURRENT")
    current_dict = json.loads(current["SecretString"])
    
    # Connect with CURRENT credentials and update password
    conn = psycopg2.connect(
        host=current_dict["host"],
        user=current_dict["username"],
        password=current_dict["password"],
        database=current_dict["dbname"],
    )
    
    with conn.cursor() as cur:
        cur.execute(
            f"ALTER USER {pending_dict['username']} WITH PASSWORD %s",
            (pending_dict["password"],)
        )
    conn.commit()
    conn.close()

def test_secret(arn, token):
    """Verify new credentials work"""
    pending = secrets_client.get_secret_value(SecretId=arn, VersionStage="AWSPENDING")
    pending_dict = json.loads(pending["SecretString"])
    
    # Try to connect with new password
    conn = psycopg2.connect(
        host=pending_dict["host"],
        user=pending_dict["username"],
        password=pending_dict["password"],
        database=pending_dict["dbname"],
    )
    conn.close()  # If this works, all good

def finish_secret(arn, token):
    """Promote AWSPENDING to AWSCURRENT"""
    metadata = secrets_client.describe_secret(SecretId=arn)
    
    # Find AWSCURRENT version
    current_version_id = None
    for version, stages in metadata["VersionIdsToStages"].items():
        if "AWSCURRENT" in stages and version != token:
            current_version_id = version
            break
    
    # Move AWSCURRENT label to new version
    secrets_client.update_secret_version_stage(
        SecretId=arn,
        VersionStage="AWSCURRENT",
        MoveToVersionId=token,
        RemoveFromVersionId=current_version_id,
    )
```

---

## 6. ☸️ Kubernetes External Secrets

### `kubernetes/external-secrets.yaml`

```yaml
# Install External Secrets Operator
# https://external-secrets.io/

apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: production
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "kv"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "my-app-role"
          serviceAccountRef:
            name: "my-app"

---
# Sync vault secret to K8s secret
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-app-secrets
  namespace: production
spec:
  refreshInterval: 1h  # Re-fetch every hour
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: my-app-secret  # Creates this K8s secret
    creationPolicy: Owner
  data:
    - secretKey: db-password
      remoteRef:
        key: myapp/database
        property: password
    - secretKey: stripe-key
      remoteRef:
        key: myapp/api
        property: stripe_key
    - secretKey: jwt-secret
      remoteRef:
        key: myapp/jwt
        property: signing_key

---
# Use the secret in your deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: production
spec:
  template:
    spec:
      containers:
      - name: app
        image: my-app:latest
        env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: my-app-secret
              key: db-password
        - name: STRIPE_KEY
          valueFrom:
            secretKeyRef:
              name: my-app-secret
              key: stripe-key
```

### Sealed Secrets (GitOps-friendly)

```yaml
# Encrypted secrets safe to commit to git!
# Encrypted by Sealed Secrets controller's public key
# Only the controller can decrypt
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: my-app-secret
  namespace: production
spec:
  encryptedData:
    db-password: AgBy3i4OJSWK+PiTySYZZA9rO43cGDEQAx...
    stripe-key: AgC8mn2VW9k8Xj3PkNm4LqP3RR5jVK...
```

---

## 7. 🔄 Refresh Token Rotation with Reuse Detection

### `refresh_tokens/manager.py`

```python
"""
Refresh token rotation with REUSE DETECTION.
If old token is used after rotation → DETECTED → all tokens revoked.
"""
import secrets
import time
from typing import Optional
from dataclasses import dataclass

@dataclass
class TokenFamily:
    """Tracks family of refresh tokens for a user"""
    user_id: int
    family_id: str
    current_token_hash: str
    issued_at: float
    used: bool = False

class RefreshTokenManager:
    """
    Manages refresh tokens with:
    - Rotation on every use
    - Reuse detection (compromise indicator)
    - Family-level revocation
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def issue_token(self, user_id: int, family_id: str = None) -> str:
        """Issue new refresh token"""
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        if not family_id:
            family_id = secrets.token_urlsafe(16)
        
        family = TokenFamily(
            user_id=user_id,
            family_id=family_id,
            current_token_hash=token_hash,
            issued_at=time.time(),
        )
        
        # Store family info
        await self.redis.setex(
            f"refresh_family:{family_id}",
            86400 * 30,  # 30 days
            json.dumps(family.__dict__),
        )
        
        # Mark token as valid
        await self.redis.setex(
            f"refresh_token:{token_hash}",
            86400 * 30,
            family_id,
        )
        
        return token
    
    async def use_token(self, token: str) -> tuple[bool, Optional[int]]:
        """
        Use refresh token to get new tokens.
        
        Returns: (success, user_id if success else None)
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Look up family
        family_id_raw = await self.redis.get(f"refresh_token:{token_hash}")
        if not family_id_raw:
            # Token doesn't exist - maybe expired
            return False, None
        
        family_id = family_id_raw.decode() if isinstance(family_id_raw, bytes) else family_id_raw
        family_raw = await self.redis.get(f"refresh_family:{family_id}")
        if not family_raw:
            return False, None
        
        family_data = json.loads(family_raw)
        
        # ── REUSE DETECTION ──
        if family_data["used"]:
            # Token was already used → COMPROMISE!
            # Someone has the old token AND used it after rotation
            print(f"🚨 SECURITY: Refresh token reuse detected for user {family_data['user_id']}!")
            await self._revoke_family(family_id)
            return False, None
        
        # Check it's the current token in family
        if family_data["current_token_hash"] != token_hash:
            # This is an OLD token (already rotated)
            # If it's still valid (not yet expired), this is REUSE
            print(f"🚨 SECURITY: Old refresh token used for user {family_data['user_id']}!")
            await self._revoke_family(family_id)
            return False, None
        
        # Mark as used
        family_data["used"] = True
        await self.redis.setex(
            f"refresh_family:{family_id}",
            86400 * 30,
            json.dumps(family_data),
        )
        
        # Issue new token (rotation!)
        new_token = await self.issue_token(family_data["user_id"], family_id)
        
        return True, family_data["user_id"]
    
    async def _revoke_family(self, family_id: str):
        """Revoke ALL tokens in family (compromise response)"""
        await self.redis.delete(f"refresh_family:{family_id}")
        # In production: also delete all token_hashes that belong to family
        # (could maintain reverse index)
        
        # Log security event
        # Trigger user notification: "Suspicious activity detected, please re-login"
```

---

## 8. 🔒 Envelope Encryption

### `encryption/envelope.py`

```python
"""
Envelope encryption: encrypt data with data key,
encrypt data key with master key (KMS).

Benefits:
- Master key never leaves KMS
- Data keys are short-lived
- Can re-encrypt large data without re-encrypting actual data
"""
import boto3
from cryptography.fernet import Fernet
import base64
from dataclasses import dataclass

@dataclass
class EncryptedData:
    """Encrypted blob with metadata"""
    ciphertext: str             # Encrypted data
    encrypted_data_key: str     # Data key encrypted by KMS
    kms_key_id: str             # Which master key

class EnvelopeEncryption:
    """
    Encrypts large data using envelope encryption pattern.
    """
    
    def __init__(self, kms_key_id: str, region: str = "us-east-1"):
        self.kms = boto3.client("kms", region_name=region)
        self.kms_key_id = kms_key_id
    
    def encrypt(self, plaintext: bytes) -> EncryptedData:
        """
        1. Generate a new data key (256-bit AES)
        2. KMS encrypts the data key with master key
        3. Use plain data key to encrypt actual data (fast, local)
        4. Return: encrypted data + encrypted data key
        """
        # 1. Generate data key from KMS
        response = self.kms.generate_data_key(
            KeyId=self.kms_key_id,
            KeySpec="AES_256",
        )
        
        plain_data_key = response["Plaintext"]
        encrypted_data_key = response["CiphertextBlob"]
        
        # 2. Encrypt data with plain data key (locally, fast)
        cipher = Fernet(base64.urlsafe_b64encode(plain_data_key[:32]))
        ciphertext = cipher.encrypt(plaintext)
        
        # 3. Return both
        return EncryptedData(
            ciphertext=base64.b64encode(ciphertext).decode(),
            encrypted_data_key=base64.b64encode(encrypted_data_key).decode(),
            kms_key_id=self.kms_key_id,
        )
    
    def decrypt(self, encrypted: EncryptedData) -> bytes:
        """
        1. KMS decrypts the data key
        2. Use plain data key to decrypt actual data
        """
        # 1. KMS decrypts data key
        encrypted_data_key = base64.b64decode(encrypted.encrypted_data_key)
        response = self.kms.decrypt(CiphertextBlob=encrypted_data_key)
        plain_data_key = response["Plaintext"]
        
        # 2. Decrypt data
        cipher = Fernet(base64.urlsafe_b64encode(plain_data_key[:32]))
        ciphertext = base64.b64decode(encrypted.ciphertext)
        return cipher.decrypt(ciphertext)

# Usage
envelope = EnvelopeEncryption(kms_key_id="arn:aws:kms:us-east-1:123:key/abc-def")

# Encrypt sensitive document
sensitive_doc = b"This is highly confidential information..."
encrypted = envelope.encrypt(sensitive_doc)

# Store in DB
db.save({"data": encrypted.ciphertext, "key": encrypted.encrypted_data_key})

# Later, decrypt
retrieved = db.load(...)
decrypted = envelope.decrypt(EncryptedData(
    ciphertext=retrieved["data"],
    encrypted_data_key=retrieved["key"],
    kms_key_id="...",
))
```

---

## 9. 🔍 Secret Leak Detection

### Pre-Commit Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args:
          - '--baseline'
          - '.secrets.baseline'
        exclude: package-lock.json|yarn.lock

  - repo: https://github.com/trufflesecurity/trufflehog
    rev: main
    hooks:
      - id: trufflehog
        args:
          - 'git'
          - '--since-commit=HEAD~1'
          - '--only-verified'
          - '--fail'

  - repo: https://github.com/zricethezav/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
```

### Initialize Baseline

```bash
# Create baseline of EXISTING secrets (acknowledged false positives)
$ detect-secrets scan > .secrets.baseline

# Audit baseline to mark which are real vs false positives
$ detect-secrets audit .secrets.baseline

# Install pre-commit
$ pre-commit install

# Now every commit will be scanned!
```

### CI Workflow

```yaml
# .github/workflows/secret-scan.yml
name: Secret Scanning

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for thorough scan
      
      - name: TruffleHog
        uses: trufflesecurity/trufflehog@main
        with:
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
          extra_args: --debug --only-verified --fail
      
      - name: Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Snyk Code Security
        uses: snyk/actions/python@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          command: code test
```

### Log Scrubbing

```python
"""
Scrub sensitive data from logs before they're persisted.
"""
import re
import logging

SENSITIVE_PATTERNS = [
    # Credit cards
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "[CARD]"),
    
    # SSN
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    
    # API keys (common patterns)
    (re.compile(r"sk_live_[a-zA-Z0-9]{20,}"), "[STRIPE_KEY]"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "[GITHUB_TOKEN]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[AWS_KEY]"),
    
    # JWT
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[JWT]"),
    
    # Bearer tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"), "Bearer [TOKEN]"),
    
    # Email (might be PII)
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
]

class ScrubbingFilter(logging.Filter):
    """Logging filter that scrubs sensitive data"""
    
    def filter(self, record):
        if isinstance(record.msg, str):
            scrubbed = record.msg
            for pattern, replacement in SENSITIVE_PATTERNS:
                scrubbed = pattern.sub(replacement, scrubbed)
            record.msg = scrubbed
        
        if record.args:
            scrubbed_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern, replacement in SENSITIVE_PATTERNS:
                        arg = pattern.sub(replacement, arg)
                scrubbed_args.append(arg)
            record.args = tuple(scrubbed_args)
        
        return True

# Install filter
logger = logging.getLogger()
logger.addFilter(ScrubbingFilter())

# Now logs are auto-scrubbed
logger.info("User credit card: 4532-1234-5678-9012")
# Logged as: "User credit card: [CARD]"
```

---

## 10. 🚨 Incident Response Runbook

### `incident_response/runbook.md`

```markdown
# 🚨 Secret Leak Incident Response

## Severity Levels
- **CRITICAL**: Production credentials, root access, DB passwords
- **HIGH**: User access tokens, API keys with sensitive scope
- **MEDIUM**: Test credentials, limited-scope keys
- **LOW**: Public keys, expired credentials

## Response (within 15 min)

### Step 1: ROTATE IMMEDIATELY (within 5 min)

```bash
# AWS keys
aws iam delete-access-key --access-key-id AKIA... --user-name compromised-user
aws iam create-access-key --user-name compromised-user

# Database passwords
vault write -force database/rotate-role/my-app-role

# JWT signing keys
vault write transit/keys/jwt-signing/rotate

# API keys
./scripts/rotate-api-key.sh KEY_ID
```

### Step 2: ASSESS DAMAGE (within 30 min)

```bash
# Check CloudTrail for unauthorized AWS API calls
aws logs tail /aws/cloudtrail --since 24h | grep COMPROMISED_KEY

# Check application logs
kubectl logs deployment/my-app --since=24h | grep -i "compromised_key"

# Check DB audit logs
SELECT * FROM audit_log 
WHERE used_credential = 'COMPROMISED_KEY' 
ORDER BY timestamp DESC;
```

### Step 3: NOTIFY (within 1 hour)

- [ ] Security team
- [ ] Engineering manager
- [ ] Compliance officer (if PII access)
- [ ] CTO (if CRITICAL)
- [ ] Customers (if GDPR breach - 72h requirement)

### Step 4: REMEDIATE (within 24 hours)

- [ ] Patch the leak source
- [ ] Add detection to prevent recurrence
- [ ] Update access controls
- [ ] Force re-login for affected users (if needed)

### Step 5: POSTMORTEM (within 1 week)

Use blameless postmortem template:
- What happened?
- When did it happen?
- How did we detect it?
- What was the impact?
- Root cause analysis
- Action items to prevent recurrence

## Contact Information

- Security on-call: PagerDuty #security-oncall
- Engineering lead: @eng-lead (Slack)
- Compliance: compliance@company.com
- External: security@company.com (for partner notifications)
```

### Automated Detection Script

```python
"""Detect public exposure of secrets"""
import requests
import re

def check_github_for_leak(secret_pattern: str, org: str = None):
    """Check if our secrets appear publicly on GitHub"""
    # Use GitHub Code Search API
    response = requests.get(
        "https://api.github.com/search/code",
        params={"q": secret_pattern},
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
    )
    
    if response.status_code == 200:
        items = response.json().get("items", [])
        if items:
            return [
                {"repo": item["repository"]["full_name"], "url": item["html_url"]}
                for item in items
            ]
    return []

# Run periodically
known_secret_prefixes = ["sk_live_", "AKIA", "ghp_"]
for prefix in known_secret_prefixes:
    leaks = check_github_for_leak(f"{prefix}company-specific-pattern")
    if leaks:
        print(f"🚨 LEAK DETECTED: {leaks}")
        # Trigger incident response
```

---

## 11. Key Learnings Summary

```
✅ HashiCorp Vault for self-hosted secrets management
✅ AWS Secrets Manager for AWS-native workloads
✅ Dynamic DB credentials = no static passwords
✅ K8s External Secrets for GitOps workflows
✅ Refresh token rotation with reuse detection
✅ Envelope encryption for large data
✅ Pre-commit + CI secret scanning
✅ Log scrubbing prevents accidental leaks
✅ Incident response runbook ready

🎯 Production secrets stack:
   - Vault for secret storage
   - External Secrets Operator for K8s sync
   - KMS for encryption
   - Rotation Lambda for AWS RDS
   - Pre-commit + CI for detection
   - Audit log + SIEM for monitoring
   - Runbook for incident response
```

---

## 🎬 What's Next?

In **Lecture 5**, we'll wrap up with **Real-World Security Scenarios** — OWASP Top 10 walkthroughs and how they manifest in real breaches.

> **Next lecture:** [05_Real_World_Security_OWASP.md](05_Real_World_Security_OWASP.md)

---

## 📚 Try It Yourself

1. Set up **complete Vault** with multiple secrets engines
2. Implement **rotation Lambda** for your AWS RDS instance
3. Build **secret leak alert** that scans GitHub for exposure
4. Add **field-level encryption** for PII in your DB
5. Run a **secret rotation game day** to test runbook
