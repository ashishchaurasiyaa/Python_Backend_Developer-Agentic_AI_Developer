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
