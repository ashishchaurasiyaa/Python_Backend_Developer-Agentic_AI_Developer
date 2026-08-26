# Microsoft Azure Fundamentals

## Why Azure (Indian Market Context)

| Company Type | Cloud Used |
|-------------|-----------|
| Indian IT Giants (TCS, Infosys, Wipro, HCL, Accenture India) | Azure-heavy (Microsoft enterprise contracts) |
| Indian Startups (CRED, Razorpay, Zepto) | AWS or GCP |
| Banking / BFSI (HDFC, ICICI, Kotak) | Azure (Microsoft compliance + partnerships) |
| MNC India Offices (Microsoft, ThoughtWorks, Capgemini) | Azure |

**Bottom line:** If you target an IT services company or BFSI in India, Azure knowledge is more valuable than AWS.

---

## Azure vs AWS — Concept Mapping

| Concept | AWS | Azure |
|---------|-----|-------|
| Virtual Machine | EC2 | Azure VM |
| Serverless | Lambda | Azure Functions |
| Container Service | ECS | Azure Container Instances (ACI) |
| Kubernetes | EKS | AKS (Azure Kubernetes Service) |
| Object Storage | S3 | Azure Blob Storage |
| Relational DB | RDS | Azure SQL Database / Azure Database for PostgreSQL |
| NoSQL | DynamoDB | CosmosDB |
| Cache | ElastiCache | Azure Cache for Redis |
| Message Queue | SQS | Azure Service Bus / Azure Queue Storage |
| Event Streaming | Kinesis | Azure Event Hubs |
| CDN | CloudFront | Azure CDN / Azure Front Door |
| DNS | Route 53 | Azure DNS |
| Load Balancer | ALB/NLB | Azure Load Balancer / Application Gateway |
| Identity | IAM | Azure Active Directory (Entra ID) |
| Secrets | Secrets Manager | Azure Key Vault |
| CI/CD | CodePipeline | Azure Pipelines (Azure DevOps) |
| Container Registry | ECR | Azure Container Registry (ACR) |
| Monitoring | CloudWatch | Azure Monitor + Application Insights |
| Logging | CloudWatch Logs | Log Analytics Workspace |
| IaC | CloudFormation | ARM Templates / Bicep / Terraform |
| LLM / AI | Bedrock | Azure OpenAI Service |

---

## Azure Account Structure

```
Azure Account (Billing)
└── Management Group (optional, for enterprises)
    └── Subscription  ← billing boundary, like AWS account
        └── Resource Group  ← logical container for resources
            ├── Virtual Machine
            ├── Storage Account
            ├── Database
            └── ...
```

Key difference from AWS: **Resource Groups** are mandatory. Every resource belongs to a Resource Group.

---

## Azure Resource Manager (ARM) — the Engine Under Every `az`/Bicep/Terraform Deployment

Every single way you touch Azure — the `az` CLI, the Portal, a Bicep file, Terraform's
`azurerm` provider — is just a different client calling the **same ARM REST API**. Understanding
what ARM does with a deployment is what separates "I ran `az deployment group create`" from
actually knowing why it worked (or why it silently deleted something).

### What happens when you submit a template

```
1. Template submitted (JSON, or Bicep compiled to JSON first — see below)
2. ARM parses resource declarations + dependencies
     explicit:  "dependsOn": ["Microsoft.Network/virtualNetworks/myVnet"]
     implicit:  a property reference like vnet.id inside another resource block
3. ARM builds a DEPENDENCY GRAPH from these, then topologically orders operations
     (VNet must exist before a subnet inside it is created, etc.)
4. For each resource, ARM calls that resource TYPE's own Resource Provider —
   Microsoft.Compute handles VMs, Microsoft.Storage handles storage accounts,
   Microsoft.Network handles VNets/NSGs — ARM itself doesn't know how to build
   a VM, it delegates to the provider and tracks the result
5. ARM PUT calls are idempotent — resubmitting the same template re-converges
   any drifted resource back to the declared state (same idea as Terraform's
   plan/apply reconciliation — in fact Terraform's azurerm provider is doing
   nothing more than making these same ARM calls on your behalf)
```

### Deployment mode — the gotcha that isn't obvious from the CLI flag name

```bash
az deployment group create --mode Incremental ...   # DEFAULT
az deployment group create --mode Complete ...       # dangerous if misunderstood
```

```
Incremental (default) → ARM only touches resources LISTED in the template.
                         Anything else already in the Resource Group is left alone.

Complete               → ARM DELETES any resource in the Resource Group that is
                          NOT declared in the template. If someone hand-created
                          a resource in that group outside the pipeline (a debug
                          VM, a manually-added storage account), a Complete
                          deployment removes it — no warning beyond the CLI's
                          confirmation prompt.
```

**Real incident shape:** a team runs `--mode Complete` against a shared Resource Group that
also has a hand-provisioned Key Vault someone set up for a one-off migration script — that Key
Vault, and every secret in it, disappears on the next pipeline run. This is why production
pipelines almost always use `Incremental` and give shared infrastructure its own dedicated
Resource Group instead of relying on Complete mode to "clean up."

### Bicep is not a separate runtime — it compiles to the same JSON

```bash
az bicep build --file main.bicep   # produces main.json — inspect it, it's plain ARM JSON
az deployment group create --template-file main.bicep ...
   # ↑ transparently runs the same compile step first, then submits the JSON.
   # ARM never sees or executes Bicep syntax directly.
```

Bicep exists purely as author-side ergonomics (shorter syntax, real loops/conditionals,
type-checking at compile time) — the thing actually reconciled against Azure's state is always
ARM JSON, exactly as if you'd hand-written it.

---

## Azure Regions

```bash
# Popular Azure regions for India
East Asia       — Hong Kong
Southeast Asia  — Singapore (closest to India, lowest latency)
Central India   — Pune (data residency for Indian compliance)
South India     — Chennai
West India      — Mumbai (most popular for Indian workloads)
```

---

## Core Azure Services for Backend Developers

### 1. Azure Virtual Machines
```bash
# Install Azure CLI
brew install azure-cli

# Login
az login

# Create resource group
az group create --name myResourceGroup --location westindia

# Create VM (Ubuntu)
az vm create \
  --resource-group myResourceGroup \
  --name myVM \
  --image Ubuntu2204 \
  --admin-username azureuser \
  --generate-ssh-keys \
  --size Standard_B2s

# Open port 80
az vm open-port --port 80 --resource-group myResourceGroup --name myVM

# Get public IP
az vm show --resource-group myResourceGroup --name myVM \
  --show-details --query publicIps -o tsv

# SSH into VM
ssh azureuser@<public-ip>
```

### 2. Azure App Service (Platform as a Service — deploy code without managing VMs)
```bash
# Create App Service Plan (the VM behind the scenes)
az appservice plan create \
  --name myPlan \
  --resource-group myResourceGroup \
  --sku B1 \              # B1=Basic, P1V3=Production
  --is-linux

# Create Web App (Python/FastAPI)
az webapp create \
  --resource-group myResourceGroup \
  --plan myPlan \
  --name my-fastapi-app \
  --runtime "PYTHON|3.11"

# Deploy from Git
az webapp deployment source config \
  --name my-fastapi-app \
  --resource-group myResourceGroup \
  --repo-url https://github.com/yourorg/your-repo \
  --branch main \
  --manual-integration

# Set environment variables
az webapp config appsettings set \
  --resource-group myResourceGroup \
  --name my-fastapi-app \
  --settings DATABASE_URL="postgresql://..." OPENAI_API_KEY="sk-..."
```

### 3. Azure Kubernetes Service (AKS)
```bash
# Create AKS cluster
az aks create \
  --resource-group myResourceGroup \
  --name myAKSCluster \
  --node-count 2 \
  --node-vm-size Standard_B2s \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials (configures kubectl)
az aks get-credentials --resource-group myResourceGroup --name myAKSCluster

# Verify
kubectl get nodes

# Deploy your app (same kubectl commands as any K8s)
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

### 4. Azure Container Registry (ACR)
```bash
# Create registry
az acr create \
  --resource-group myResourceGroup \
  --name myContainerRegistry \
  --sku Basic

# Login to registry
az acr login --name myContainerRegistry

# Tag and push image
docker tag myapp:latest mycontainerregistry.azurecr.io/myapp:latest
docker push mycontainerregistry.azurecr.io/myapp:latest

# Grant AKS permission to pull from ACR
az aks update \
  --name myAKSCluster \
  --resource-group myResourceGroup \
  --attach-acr myContainerRegistry
```

### 5. Azure Blob Storage (equivalent to S3)
```python
# pip install azure-storage-blob

from azure.storage.blob import BlobServiceClient

connection_string = "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=..."
client = BlobServiceClient.from_connection_string(connection_string)

container_client = client.get_container_client("mycontainer")

# Upload file
with open("document.pdf", "rb") as f:
    container_client.upload_blob("uploads/document.pdf", f, overwrite=True)

# Download file
blob = container_client.get_blob_client("uploads/document.pdf")
with open("downloaded.pdf", "wb") as f:
    f.write(blob.download_blob().readall())

# Generate SAS URL (pre-signed URL equivalent)
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta

sas_token = generate_blob_sas(
    account_name="mystorageaccount",
    container_name="mycontainer",
    blob_name="uploads/document.pdf",
    account_key="...",
    permission=BlobSasPermissions(read=True),
    expiry=datetime.utcnow() + timedelta(hours=1)
)
url = f"https://mystorageaccount.blob.core.windows.net/mycontainer/uploads/document.pdf?{sas_token}"
```

### 6. Azure Database for PostgreSQL
```bash
# Create flexible server (recommended over single server)
az postgres flexible-server create \
  --resource-group myResourceGroup \
  --name mypostgresserver \
  --location westindia \
  --admin-user myadmin \
  --admin-password MySecurePassword123! \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 16 \
  --storage-size 32

# Allow your IP
az postgres flexible-server firewall-rule create \
  --resource-group myResourceGroup \
  --name mypostgresserver \
  --rule-name AllowMyIP \
  --start-ip-address <your-ip> \
  --end-ip-address <your-ip>

# Connection string for Python
# postgresql://myadmin:password@mypostgresserver.postgres.database.azure.com:5432/postgres?sslmode=require
```

### 7. Azure Cache for Redis
```bash
# Create Redis cache
az redis create \
  --name myRedisCache \
  --resource-group myResourceGroup \
  --location westindia \
  --sku Basic \
  --vm-size C0

# Get connection string
az redis list-keys --name myRedisCache --resource-group myResourceGroup
```

```python
# pip install redis

import redis

r = redis.Redis(
    host="myRedisCache.redis.cache.windows.net",
    port=6380,
    password="<access-key>",
    ssl=True
)

r.set("key", "value", ex=3600)   # TTL 1 hour
print(r.get("key"))
```

### 8. Azure Service Bus (equivalent to SQS + RabbitMQ)
```python
# pip install azure-servicebus

from azure.servicebus import ServiceBusClient, ServiceBusMessage

connection_str = "Endpoint=sb://..."
queue_name = "my-queue"

# Send message
with ServiceBusClient.from_connection_string(connection_str) as client:
    with client.get_queue_sender(queue_name) as sender:
        message = ServiceBusMessage('{"task": "send_email", "to": "user@example.com"}')
        sender.send_messages(message)

# Receive message
with ServiceBusClient.from_connection_string(connection_str) as client:
    with client.get_queue_receiver(queue_name) as receiver:
        for msg in receiver.receive_messages(max_wait_time=5):
            print(str(msg))
            receiver.complete_message(msg)   # acknowledge = delete from queue
```

---

## Azure Identity — Entra ID (formerly Azure AD)

The most important Azure concept for enterprises:

```
Entra ID (Azure AD) = Azure's IAM + Directory Service
├── Users         — human accounts
├── Service Principals — app accounts (like IAM roles for apps)
├── Managed Identity   — no credentials needed (auto-rotated)
└── Groups        — collection of users/apps
```

### How Managed Identity Actually Authenticates (the IMDS token flow)

`DefaultAzureCredential()` looks like magic — no key, no secret, it just works. Here's what it's
actually doing:

```
1. Every Azure VM / App Service / AKS node has a LOCAL-ONLY metadata endpoint:
     http://169.254.169.254/metadata/identity/oauth2/token?resource=<target-uri>
   This IP is only reachable FROM INSIDE that specific instance — the Azure
   fabric controller (hypervisor-level networking) is what gates it, not a
   password. That's the actual trust mechanism: "you can only be asking
   from inside the one VM this identity is attached to."

2. The SDK calls that local endpoint, asking for a token scoped to ONE
   target resource (e.g. resource=https://vault.azure.net).

3. IMDS returns a short-lived Entra ID–issued OAuth2 access token — scoped
   ONLY to that resource. Unlike an AWS STS session credential (which is a
   general-purpose signing credential usable for any API call the role
   permits), an Azure Managed Identity token is fetched per target resource
   — asking Key Vault and Storage in the same request needs two separate
   IMDS calls, one per `resource=` value.

4. That token is sent to the target service: Authorization: Bearer <token>

5. The target service (Key Vault, Storage, etc.) validates the token's
   signature against Entra ID's public signing keys, extracts the calling
   identity's object ID, and checks: does this object ID have an RBAC role
   assignment on THIS resource granting the requested action?
```

`DefaultAzureCredential` is just this IMDS call wrapped with caching + a fallback chain (tries
Managed Identity first, then `az login` CLI credentials for local dev, then environment
variables) — same "credential resolution order" idea AWS's SDK does, different mechanism
underneath.

**Managed Identity (best practice — no secrets in code):**
```python
# pip install azure-identity azure-keyvault-secrets

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# DefaultAzureCredential automatically uses:
# - Managed Identity (in Azure)
# - Azure CLI credentials (local dev)
# - Environment variables (CI)
credential = DefaultAzureCredential()

client = SecretClient(
    vault_url="https://my-keyvault.vault.azure.net/",
    credential=credential
)

secret = client.get_secret("database-password")
print(secret.value)   # no hardcoded credentials anywhere
```

**Azure RBAC roles (most common):**
| Role | What it can do |
|------|---------------|
| Owner | Full access including permissions |
| Contributor | Create/manage resources, no permissions |
| Reader | View only |
| AcrPull | Pull images from Container Registry |
| Storage Blob Data Contributor | Read/write Blob Storage |

### RBAC Evaluation Model — and the Trap for Anyone Coming from AWS

```
Scope hierarchy (role assignments INHERIT downward):
  Management Group
    └── Subscription
          └── Resource Group
                └── Resource

A "Contributor" assignment at Subscription scope silently applies to every
Resource Group and every Resource beneath it — assign at the narrowest
scope that actually needs it, same "least privilege" idea as AWS, but the
inheritance direction is the thing to keep straight in your head.
```

**The actual trap:** AWS IAM has an explicit `Deny` that always wins over any `Allow`, even one
granted by a completely different policy. **Azure RBAC has no equivalent explicit Deny in the
normal role-assignment model** — evaluation is closer to "union of every applicable Allow grant
across every inherited scope, nothing subtracts from it." The only way to carve out an exception
is a separate, rarely-used mechanism (a **Deny assignment**, reserved for Azure Blueprints /
Landing Zone guardrails, or an ABAC condition attached to the specific role assignment) — most
teams never touch either. So "I'll just Deny this one action" — the reflexive AWS move — has no
direct Azure equivalent; the fix is almost always to narrow the scope or split the role
assignment instead.

---

## Azure Key Vault (Secrets Management)
```bash
# Create Key Vault
az keyvault create \
  --name myKeyVault \
  --resource-group myResourceGroup \
  --location westindia

# Store secret
az keyvault secret set \
  --vault-name myKeyVault \
  --name "database-password" \
  --value "MySecurePassword123!"

# Grant App Service access to Key Vault
az keyvault set-policy \
  --name myKeyVault \
  --object-id <app-managed-identity-object-id> \
  --secret-permissions get list
```

---

## Azure Monitor + Application Insights

```python
# pip install opencensus-ext-azure

from opencensus.ext.azure import metrics_exporter
from opencensus.stats import aggregation, measure, stats, view

# OR use OpenTelemetry (preferred in 2026)
# pip install azure-monitor-opentelemetry

from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    connection_string="InstrumentationKey=..."
)
# All traces, logs, metrics now go to Application Insights
```

---

## Azure DevOps (CI/CD — alternative to GitHub Actions)

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
      - main

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '3.11'

- script: |
    pip install -r requirements.txt
    pytest tests/
  displayName: 'Run tests'

- task: Docker@2
  inputs:
    containerRegistry: 'myACRServiceConnection'
    repository: 'myapp'
    command: 'buildAndPush'
    tags: '$(Build.BuildId)'

- task: KubernetesManifest@0
  inputs:
    action: 'deploy'
    kubernetesServiceConnection: 'myAKSConnection'
    manifests: 'k8s/deployment.yaml'
    containers: 'myregistry.azurecr.io/myapp:$(Build.BuildId)'
```

---

## Azure OpenAI Service (AI Track)

```python
# pip install openai  (same SDK — just different base_url)

from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint="https://my-openai.openai.azure.com/",
    api_key="...",
    api_version="2024-02-01"
)

response = client.chat.completions.create(
    model="gpt-4o",          # deployment name in Azure (not model name)
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is AKS?"}
    ]
)
print(response.choices[0].message.content)
```

---

## Key Interview Questions

**Q: What is a Resource Group in Azure?**
A logical container for resources in a subscription. All resources in a Resource Group share the same lifecycle — you can delete the whole group to clean up. Helps with billing, access control, and tagging.

**Q: What is Managed Identity and why use it?**
A system-assigned or user-assigned identity for Azure resources. Eliminates the need for credentials in code — Azure automatically provides and rotates tokens. Best practice for any Azure app.

**Q: AKS vs ACI (Azure Container Instances)?**
ACI = run a single container quickly (no cluster management, pay per second). AKS = full Kubernetes cluster (production, auto-scaling, complex apps). Use ACI for jobs/scripts, AKS for production services.

**Q: Azure Service Bus vs Azure Event Hubs?**
Service Bus = message queue (guaranteed delivery, ordering, dead-letter). Event Hubs = event streaming (Kafka-compatible, high throughput, 90-day retention). Use Service Bus for task queues, Event Hubs for telemetry/analytics.

**Q: How is Azure Blob Storage different from S3?**
Conceptually identical. Azure uses Container (≈ S3 bucket) and Blob (≈ S3 object). Storage Account is the top-level resource. Pricing and performance tiers differ slightly.

**Q: Someone reran a deployment and now a hand-created resource in the same Resource Group is gone. What happened?**
The deployment ran with `--mode Complete`, not the default `Incremental`. Complete mode deletes any resource in the target Resource Group that isn't declared in the template — it's a reconciliation-to-exact-match operation, not an additive one. Fix going forward: keep shared/manually-managed infrastructure in its own Resource Group, never one a Complete-mode pipeline also owns.

**Q: A pod on AKS can't authenticate to Key Vault even though `DefaultAzureCredential()` "should just work." Where do you look first?**
Confirm the identity actually has a role assignment on that Key Vault — `DefaultAzureCredential` will happily fetch a valid, well-signed token via IMDS, but a valid token isn't the same as an authorized one. The token proves *who* is asking; Key Vault's own RBAC check (or legacy access policy) decides *what* they're allowed to do. `az role assignment list --scope <vault-resource-id>` is the equivalent of AWS's `aws sts get-caller-identity` here — it tells you what the identity can actually do, not just that it authenticated.

---

## Related

- [02_azure_devops_python.md](02_azure_devops_python.md) — AKS deployment, control-plane mechanics, ACR pull via Managed Identity
- [../08_Terraform/01_terraform_iac.md](../08_Terraform/01_terraform_iac.md) — the same declarative-reconciliation idea, provider-agnostic
- [../07_Cloud_AWS/01_iam_compute_ec2.md](../07_Cloud_AWS/01_iam_compute_ec2.md) — direct comparison: STS temporary credentials vs Managed Identity's IMDS token flow
