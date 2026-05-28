# Secrets Management Advanced — Vault, AWS Secrets Manager, K8s Secrets

## Quick Concepts

**WHAT:**
- **Secrets** = passwords, API keys, certs, encryption keys
- **Static secrets** = manually set, rotate periodically
- **Dynamic secrets** = generated per request (Vault feature)
- **AWS Secrets Manager** = managed secret store with rotation
- **AWS Parameter Store** = config + secrets (cheaper)
- **HashiCorp Vault** = self-hosted with dynamic secrets
- **Sealed Secrets / SOPS** = encrypted secrets in Git (GitOps)

**WHY secrets management matters:**
- Hardcoded secrets in code = repo leak = breach
- Env vars in container = visible in process listing
- Plain text config = anyone with access reads
- Need: encrypted at rest, encrypted in transit, audited access, rotated

**HOW secrets layers stack:**

```
┌────────────────────────────────────────────────────────┐
│  Layer 1: Storage (AWS Secrets Manager / Vault)        │
├────────────────────────────────────────────────────────┤
│  Layer 2: Access Control (IAM, Vault policies)         │
├────────────────────────────────────────────────────────┤
│  Layer 3: Injection (env vars, files, sidecar)         │
├────────────────────────────────────────────────────────┤
│  Layer 4: Rotation (automated, no app changes)         │
├────────────────────────────────────────────────────────┤
│  Layer 5: Audit (CloudTrail, Vault audit log)          │
└────────────────────────────────────────────────────────┘
```

---

## Interview Questions & Answers

### Q1: AWS Secrets Manager — production setup + rotation?

**Answer:**

**WHAT:** Managed service for secrets storage with automatic rotation.

**WHY over Parameter Store:**
- ✅ Built-in rotation (Lambda functions)
- ✅ Cross-account access
- ✅ Cross-region replication
- ✅ Resource-level policies
- ❌ Costlier ($0.40/secret/month + API calls)

**HOW — Store secret:**

```python
import boto3

client = boto3.client("secretsmanager", region_name="ap-south-1")

# Create secret
response = client.create_secret(
    Name="myapp/prod/database",
    Description="Production database credentials",
    SecretString=json.dumps({
        "username": "admin",
        "password": "supersecret",
        "host": "myapp-db.xxx.rds.amazonaws.com",
        "port": 5432,
        "dbname": "myapp",
    }),
    Tags=[
        {"Key": "Environment", "Value": "production"},
        {"Key": "Service", "Value": "myapp"},
    ]
)

# Retrieve secret
response = client.get_secret_value(SecretId="myapp/prod/database")
secret = json.loads(response["SecretString"])
db_password = secret["password"]


# Update secret (creates new version)
client.update_secret(
    SecretId="myapp/prod/database",
    SecretString=json.dumps({
        "username": "admin",
        "password": "new-password",
        # ...
    })
)


# Get specific version
client.get_secret_value(
    SecretId="myapp/prod/database",
    VersionStage="AWSPREVIOUS"   # PREVIOUS, CURRENT, PENDING
)
```

**HOW — Auto-rotation with Lambda:**

```python
# Rotation Lambda function (AWS-provided template for RDS)
import boto3

def lambda_handler(event, context):
    """
    INTERVIEW: 4-step rotation process.
    Called by Secrets Manager during rotation.
    """
    arn = event["SecretId"]
    token = event["ClientRequestToken"]
    step = event["Step"]

    secrets_client = boto3.client("secretsmanager")

    if step == "createSecret":
        # 1. Generate new password
        new_password = generate_random_password()
        secrets_client.put_secret_value(
            SecretId=arn,
            ClientRequestToken=token,
            SecretString=json.dumps({"password": new_password, ...}),
            VersionStages=["AWSPENDING"]
        )

    elif step == "setSecret":
        # 2. Update DB with new password
        update_database_password(new_password)

    elif step == "testSecret":
        # 3. Verify new password works
        verify_database_connection(new_password)

    elif step == "finishSecret":
        # 4. Mark as current, retire old
        secrets_client.update_secret_version_stage(
            SecretId=arn,
            VersionStage="AWSCURRENT",
            MoveToVersionId=token,
            RemoveFromVersionId=current_version_id
        )
```

**HOW — Trigger rotation:**

```python
# Enable automatic rotation every 30 days
client.rotate_secret(
    SecretId="myapp/prod/database",
    RotationLambdaARN="arn:aws:lambda:..:function:RotateRDSPassword",
    RotationRules={"AutomaticallyAfterDays": 30}
)

# Manual trigger
client.rotate_secret(SecretId="myapp/prod/database")
```

**HOW — ECS Task injection:**

```json
{
  "family": "myapp",
  "containerDefinitions": [{
    "name": "app",
    "image": "myapp:latest",
    "secrets": [
      {
        "name": "DB_PASSWORD",
        "valueFrom": "arn:aws:secretsmanager:ap-south-1:123:secret:myapp/prod/database:password::"
      },
      {
        "name": "JWT_SECRET",
        "valueFrom": "arn:aws:secretsmanager:ap-south-1:123:secret:myapp/prod/jwt:value::"
      }
    ]
  }]
}
```

Format: `arn:secret:NAME:JSON_KEY:VERSION_STAGE:VERSION_ID`
- Empty `VERSION_STAGE` = AWSCURRENT
- Empty `VERSION_ID` = latest

---

### Q2: AWS Parameter Store vs Secrets Manager — kab kya?

**Answer:**

| Feature | Parameter Store | Secrets Manager |
|---|---|---|
| **Cost** | Free (Standard) / $0.05 (Advanced) | $0.40/secret/month |
| **Storage** | 4KB Standard / 8KB Advanced | 64KB |
| **Rotation** | ❌ Manual | ✅ Automatic |
| **Cross-region replication** | ❌ | ✅ |
| **Resource policy** | Advanced tier only | ✅ |
| **Versioning** | ✅ | ✅ |
| **CloudFormation integration** | ✅ Easier | ✅ |
| **Best for** | Config, non-sensitive | Sensitive secrets needing rotation |

**HOW — Parameter Store usage:**

```python
import boto3

ssm = boto3.client("ssm")

# Standard parameter (free)
ssm.put_parameter(
    Name="/myapp/prod/api_url",
    Value="https://api.example.com",
    Type="String",
)

# SecureString (encrypted with KMS)
ssm.put_parameter(
    Name="/myapp/prod/api_key",
    Value="secret-key",
    Type="SecureString",
    KeyId="alias/aws/ssm",  # Or custom KMS key
)

# Retrieve
response = ssm.get_parameter(
    Name="/myapp/prod/api_key",
    WithDecryption=True
)
value = response["Parameter"]["Value"]

# Get multiple by path
response = ssm.get_parameters_by_path(
    Path="/myapp/prod/",
    Recursive=True,
    WithDecryption=True
)
```

**Decision rule:**
- **Non-sensitive config** (URLs, feature flags) → Parameter Store Standard
- **Sensitive but rarely rotated** (API keys) → Parameter Store SecureString
- **Sensitive + rotation needed** (DB passwords) → Secrets Manager

---

### Q3: HashiCorp Vault — full setup + dynamic secrets?

**Answer:**

**WHAT:** Self-hosted secrets management with advanced features.

**WHY Vault over AWS Secrets Manager:**
- ✅ **Dynamic secrets** (generated per request, short TTL)
- ✅ Multi-cloud support
- ✅ Advanced auth methods (LDAP, Kerberos, mTLS)
- ✅ Encryption as a Service (Transit engine)
- ❌ Self-hosted ops burden

**HOW — Setup:**

```bash
# Install
brew install vault

# Start dev mode (for learning, NOT production)
vault server -dev

# Set address + token (from output)
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='dev-token-here'

# Store secret
vault kv put secret/myapp/db password="supersecret" username="admin"

# Read secret
vault kv get secret/myapp/db
vault kv get -field=password secret/myapp/db

# Read via API
curl -H "X-Vault-Token: $VAULT_TOKEN" \
  http://127.0.0.1:8200/v1/secret/data/myapp/db
```

**HOW — Python client:**

```python
# pip install hvac

import hvac

client = hvac.Client(
    url="https://vault.example.com:8200",
    token=os.environ["VAULT_TOKEN"],   # Or use auth methods
)

# KV v2 secrets
def get_secret(path: str) -> dict:
    response = client.secrets.kv.v2.read_secret_version(
        path=path,
        mount_point="secret"
    )
    return response["data"]["data"]


# Usage
db_creds = get_secret("myapp/db")
password = db_creds["password"]
```

**HOW — Dynamic database credentials (THE killer feature):**

```bash
# Enable database secrets engine
vault secrets enable database

# Configure PostgreSQL connection
vault write database/config/myapp-postgres \
    plugin_name=postgresql-database-plugin \
    allowed_roles="myapp-role" \
    connection_url="postgresql://{{username}}:{{password}}@db:5432/myapp" \
    username="vault-admin" \
    password="admin-password"

# Define role (creates DB users on demand)
vault write database/roles/myapp-role \
    db_name=myapp-postgres \
    creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
                        GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
    default_ttl="1h" \
    max_ttl="24h"

# Request credentials (Vault creates new DB user)
vault read database/creds/myapp-role
# Output:
# username  v-token-myapp-x7yz1...
# password  randompassword123
# lease_id  database/creds/myapp-role/...
# Auto-revoked after 1 hour!
```

**HOW — Vault Agent (sidecar) for K8s:**

```yaml
# Kubernetes deployment with Vault Agent sidecar
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "myapp-role"
        vault.hashicorp.com/agent-inject-secret-db-creds: "secret/myapp/db"
        vault.hashicorp.com/agent-inject-template-db-creds: |
          {{- with secret "secret/myapp/db" -}}
          DB_USERNAME={{ .Data.data.username }}
          DB_PASSWORD={{ .Data.data.password }}
          {{- end -}}
    spec:
      serviceAccountName: myapp
      containers:
        - name: app
          image: myapp:latest
          # ⭐ Secrets mounted at /vault/secrets/db-creds
          # App reads file (not env var)
```

---

### Q4: Kubernetes Secrets vs External Secrets Operator?

**Answer:**

**WHAT:**
- **K8s Secrets** = Built-in resource, base64 (NOT encrypted)
- **External Secrets Operator** = Sync from AWS Secrets Manager / Vault to K8s Secrets

**WHY K8s Secrets alone insufficient:**
- ❌ base64 ≠ encryption (anyone with kubectl can read)
- ❌ No rotation
- ❌ Not version controlled (or committed in plain)
- ✅ Encryption at rest possible (etcd encryption)

**HOW — Plain K8s Secret:**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
data:
  username: YWRtaW4=          # base64 of "admin"
  password: c3VwZXJzZWNyZXQ=  # base64 of "supersecret"
```

```yaml
# Mount in pod
spec:
  containers:
    - name: app
      env:
        - name: DB_USERNAME
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: username
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: password
```

**HOW — External Secrets Operator (recommended):**

```bash
# Install
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system --create-namespace
```

```yaml
# 1. Define SecretStore (connection to AWS Secrets Manager)
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: ap-south-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
            namespace: external-secrets-system

---
# 2. Define ExternalSecret (what to sync)
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-creds
spec:
  refreshInterval: 1h          # ⭐ Auto-refresh every hour
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: db-credentials        # ⭐ K8s Secret created with this name
    creationPolicy: Owner
  data:
    - secretKey: username
      remoteRef:
        key: myapp/prod/database
        property: username
    - secretKey: password
      remoteRef:
        key: myapp/prod/database
        property: password
```

Now your pod uses `db-credentials` K8s Secret as usual — but it's auto-synced from AWS.

---

### Q5: Sealed Secrets — GitOps workflow ke liye?

**Answer:**

**WHAT:** Encrypted secrets safe to commit to Git.

**WHY:**
- ✅ Single source of truth (Git)
- ✅ ArgoCD/Flux can deploy them
- ✅ Encrypted with cluster's public key
- ✅ Only the cluster controller can decrypt

**HOW:**

```bash
# 1. Install Sealed Secrets controller in cluster
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# 2. Install kubeseal CLI
brew install kubeseal

# 3. Create regular Secret (DON'T commit this)
cat <<EOF > secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
stringData:
  password: supersecret
EOF

# 4. Encrypt with cluster's public key
kubeseal --format=yaml < secret.yaml > sealed-secret.yaml

# 5. Sealed secret looks like:
cat sealed-secret.yaml
# apiVersion: bitnami.com/v1alpha1
# kind: SealedSecret
# metadata:
#   name: db-credentials
# spec:
#   encryptedData:
#     password: AgAhpFt+lPNT...   # Encrypted!
#   template:
#     metadata:
#       name: db-credentials

# 6. ✅ Safe to commit to Git
git add sealed-secret.yaml
git commit -m "Add DB credentials"
git push

# 7. Apply (or via ArgoCD)
kubectl apply -f sealed-secret.yaml
# Controller decrypts → creates regular Secret automatically
```

---

### Q6: SOPS (Mozilla) — encrypted YAML/JSON in Git?

**Answer:**

**WHAT:** Encrypted files with selective encryption (keys plain, values encrypted).

**WHY over Sealed Secrets:**
- ✅ Works for any file (not just K8s)
- ✅ Encrypted file readable structure (diff-friendly)
- ✅ Multi-key support (AWS KMS, GCP KMS, age, PGP)
- ✅ Used by Helmfile, Terraform, ArgoCD

**HOW:**

```bash
# Install
brew install sops age

# Generate age key (modern alternative to PGP)
age-keygen -o key.txt
# Public key: age1abc...

# Create .sops.yaml config
cat <<EOF > .sops.yaml
creation_rules:
  - path_regex: secrets/.*\.yaml$
    age: age1abc...   # Your public key
EOF

# Create secret file
cat <<EOF > secrets/db.yaml
db_password: supersecret
api_key: another-secret
EOF

# Encrypt in place
sops -e -i secrets/db.yaml

# Result (safe to commit):
cat secrets/db.yaml
# db_password: ENC[AES256_GCM,data:abc=,iv:xyz=,tag:123=,type:str]
# api_key: ENC[AES256_GCM,data:def=,iv:wxy=,tag:456=,type:str]
# sops:
#   age:
#     - recipient: age1abc...
#       enc: ...

# Edit (auto decrypts in $EDITOR)
sops secrets/db.yaml

# Decrypt for use
sops -d secrets/db.yaml > /tmp/db.yaml
```

**HOW — SOPS in CI/CD:**

```yaml
# .github/workflows/deploy.yml
- name: Decrypt secrets
  env:
    SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
  run: |
    echo "$SOPS_AGE_KEY" > /tmp/age.key
    SOPS_AGE_KEY_FILE=/tmp/age.key sops -d secrets/db.yaml > /tmp/decrypted.yaml
```

---

### Q7: Secret rotation strategy — production patterns?

**Answer:**

**HOW — Rotation patterns:**

**Pattern 1: Hot rotation (no downtime)**
```python
class RotationAwareSecretClient:
    """
    INTERVIEW: Check for new version periodically.
    """
    def __init__(self, secret_arn: str, refresh_interval: int = 300):
        self.arn = secret_arn
        self.refresh_interval = refresh_interval
        self._cached = None
        self._cached_at = 0
        self._client = boto3.client("secretsmanager")

    def get(self) -> dict:
        now = time.time()
        if not self._cached or (now - self._cached_at) > self.refresh_interval:
            response = self._client.get_secret_value(SecretId=self.arn)
            self._cached = json.loads(response["SecretString"])
            self._cached_at = now
        return self._cached


# Usage
db_secrets = RotationAwareSecretClient("myapp/prod/database")
password = db_secrets.get()["password"]
# Auto-refreshes every 5 min
```

**Pattern 2: Connection retry on auth failure**
```python
async def execute_query_with_retry(query: str):
    for attempt in range(2):
        try:
            return await db.execute(query)
        except OperationalError as e:
            if "password authentication failed" in str(e) and attempt == 0:
                # Password may have rotated — reload
                new_password = await secrets_client.get_secret_value()
                await db.reconnect(new_password)
                continue
            raise
```

**Pattern 3: Dual credentials window**
```
1. Generate new password
2. Add new password as ADDITIONAL valid credential (DB user has 2 passwords temporarily)
3. Deploy app with new password
4. Remove old password after deployment confirmed
```

---

### Q8: Local dev secrets — team workflow?

**Answer:**

**WHAT:** How developers handle secrets locally.

**Anti-patterns:**
- ❌ Slack the .env file
- ❌ Commit .env to Git
- ❌ Email the secrets

**HOW — Proper workflow:**

**Option 1: 1Password Connect (team subscription)**
```bash
# Install op CLI
brew install 1password-cli

# Inject secrets at runtime (never write to disk)
op run --env-file=.env.template -- python app.py

# .env.template (committed to Git)
DB_PASSWORD=op://Dev/myapp-db/password
API_KEY=op://Dev/stripe/api-key
```

**Option 2: Doppler (free for small teams)**
```bash
# Install
brew install dopplerhq/cli/doppler

# Login
doppler login

# Setup project
doppler setup

# Run with secrets injected
doppler run -- python app.py
```

**Option 3: direnv + .env.example**
```bash
# .env.example (commit this)
DB_PASSWORD=
API_KEY=

# .env (gitignored, copy from .example)
cp .env.example .env
# Fill in real values

# Auto-load with direnv
brew install direnv
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc

# .envrc (commit this)
dotenv .env

# Now cd into dir → secrets auto-loaded
```

---

## Secrets Management Checklist

```markdown
### Storage
- [ ] Secrets NEVER in Git (use .gitignore)
- [ ] Production secrets in Vault / Secrets Manager
- [ ] Encrypted at rest (KMS keys)
- [ ] Versioning enabled

### Access
- [ ] IAM least privilege (specific secret ARNs)
- [ ] Resource policies for cross-account
- [ ] No long-lived AWS keys (use OIDC for CI/CD)
- [ ] Service accounts (K8s) with limited scope

### Rotation
- [ ] Automated rotation for DB passwords (30-90 days)
- [ ] App handles rotation gracefully (retry on auth fail)
- [ ] Old version retained briefly (rollback)
- [ ] Rotation alerts (success + failures)

### Injection
- [ ] ECS: secrets parameter (NOT env in task def)
- [ ] K8s: External Secrets Operator
- [ ] Vault Agent sidecar (advanced)
- [ ] Never log secret values

### Audit
- [ ] CloudTrail enabled (Secrets Manager API calls)
- [ ] Vault audit log enabled
- [ ] Monthly review of access patterns
- [ ] Alert on unusual access (cross-region, new IP)

### Local Dev
- [ ] .env in .gitignore
- [ ] .env.example committed (template)
- [ ] Team sharing via 1Password / Doppler
- [ ] Pre-commit hook checks for secrets (detect-secrets, gitleaks)
```

---

## Common Pitfalls

| Pitfall | Risk | Fix |
|---|---|---|
| Hardcoded in source | Repo leak = breach | Secrets manager |
| In Docker ENV | Visible in `docker history` | BuildKit secrets / runtime injection |
| In CI/CD env vars | Logged in console | OIDC + Secrets Manager |
| K8s Secret base64 | Anyone with kubectl reads | Sealed Secrets / SOPS |
| No rotation | Long window of compromise | Auto-rotate 30-90 days |
| Same secret all envs | Dev breach = prod breach | Separate per env |
| In log statements | CloudWatch leak | Audit log statements |
| Not versioned | Can't rollback | Use versioning features |
