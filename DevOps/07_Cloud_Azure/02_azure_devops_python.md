# Azure for Python Backend + Agentic AI Developers

## Deploying FastAPI on Azure (3 ways)

### Way 1 — Azure App Service (simplest, no K8s)
```bash
# Install Azure CLI + login
az login

# Create resource group
az group create --name fastapi-prod --location westindia

# Create App Service Plan
az appservice plan create \
  --name fastapi-plan \
  --resource-group fastapi-prod \
  --sku B2 \
  --is-linux

# Create Web App
az webapp create \
  --resource-group fastapi-prod \
  --plan fastapi-plan \
  --name my-fastapi-app-2026 \
  --runtime "PYTHON|3.11"

# Set startup command (Gunicorn + Uvicorn workers)
az webapp config set \
  --resource-group fastapi-prod \
  --name my-fastapi-app-2026 \
  --startup-file "gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app"

# Deploy from GitHub (zip deploy)
az webapp up \
  --name my-fastapi-app-2026 \
  --resource-group fastapi-prod \
  --runtime PYTHON:3.11
```

### Way 2 — Docker on Azure App Service
```bash
# Build and push to ACR
az acr build \
  --registry myRegistry \
  --image fastapi-app:latest \
  .

# Deploy container to App Service
az webapp config container set \
  --name my-fastapi-app-2026 \
  --resource-group fastapi-prod \
  --docker-custom-image-name myRegistry.azurecr.io/fastapi-app:latest \
  --docker-registry-server-url https://myRegistry.azurecr.io
```

### Way 3 — AKS (production scale)
```bash
# Deploy same K8s manifests as anywhere else
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml  # with nginx-ingress or Azure Application Gateway
```

---

## AKS — What's Actually Managed, and What `--attach-acr` Really Does

### Control plane vs node pool — two different billing/ownership models

```
Control plane (API server, etcd, scheduler, controller-manager)
  → Azure-managed, you never see a VM for it, free tier available
  → this is what `kubectl` talks to — it lives outside your subscription's
    visible compute, Microsoft operates and patches it

Node pool
  → YOUR VMs, and specifically: an AKS node pool IS an Azure VM Scale Set
    (VMSS) underneath. `kubectl get nodes` output maps 1:1 to VMSS instances
    you can also see via `az vmss list`.
  → this is what you pay for, what Cluster Autoscaler resizes, and where
    kubelet actually runs
```

The Kubernetes control-plane theory itself (reconciliation loop, scheduler, watch/diff/act) is
already covered in the standalone `06_Kubernetes` phase of this track — what's Azure-specific is
how the control plane and node pool are split across Microsoft's infrastructure vs yours.

### `az aks update --attach-acr` — not a network rule, an RBAC grant

```bash
az aks update --name myAKSCluster --resource-group myResourceGroup --attach-acr myContainerRegistry
```

This does **not** open a firewall path. What it actually does: it takes the AKS cluster's
kubelet managed identity (every AKS cluster has one) and creates an RBAC role assignment —
**`AcrPull`, scoped to that specific registry** — exactly the Managed Identity + RBAC mechanism
from `01_azure_fundamentals.md`. When a node's kubelet needs to pull an image, it goes through
the same IMDS token flow described there: request a token scoped to the ACR resource, present it
to ACR, ACR checks the kubelet identity's role assignments.

**Debugging consequence:** if a pod is stuck in `ImagePullBackOff` with a 401/403 against ACR,
the useful question is *"does the kubelet identity have `AcrPull` on this registry"*
(`az role assignment list --scope <acr-resource-id>`), not "is there a network path from the
node to the registry" — ACR is a public HTTPS endpoint either way, the failure is almost always
authorization, not connectivity.

### `type: LoadBalancer` Services — where the actual Azure Load Balancer comes from

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service
spec:
  type: LoadBalancer
  ...
```

Applying this manifest doesn't create anything by itself inside Kubernetes' own object model —
AKS runs Azure's **cloud-controller-manager**, which watches the API server for `Service`
objects of type `LoadBalancer`. When it sees one, it calls the **ARM API** (the same Resource
Manager reconciliation engine from `01_azure_fundamentals.md`) to provision a real Azure Load
Balancer resource + public IP, then writes that IP back into the Service's `status`. The
Kubernetes control loop and the ARM reconciliation loop are two separate systems here, chained
together by the cloud-controller-manager watching one and calling the other.

---

## Azure Functions (Serverless — for background tasks)

```python
# function_app.py
import azure.functions as func
import logging

app = func.FunctionApp()

# HTTP trigger (like Lambda)
@app.route(route="hello")
def http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    name = req.params.get('name', 'World')
    return func.HttpResponse(f"Hello, {name}!")

# Timer trigger (like Cron / Celery Beat)
@app.timer_trigger(schedule="0 */5 * * * *")   # every 5 minutes
def timer_trigger(myTimer: func.TimerRequest) -> None:
    logging.info("Running scheduled job...")
    # send emails, clean up data, etc.

# Queue trigger (process messages from Service Bus)
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="my-queue",
    connection="ServiceBusConnection"
)
def queue_trigger(msg: func.ServiceBusMessage) -> None:
    body = msg.get_body().decode('utf-8')
    logging.info(f"Processing: {body}")
```

```bash
# Install Azure Functions Core Tools
npm install -g azure-functions-core-tools@4

# Create project
func init my-function-app --python

# Test locally
func start

# Deploy to Azure
func azure functionapp publish my-function-app-name
```

---

## Azure Complete Stack for a Python Backend App

```
┌─────────────────────────────────────────────────────────┐
│                    Azure Stack                          │
│                                                         │
│  User → Azure Front Door (CDN + WAF + Global LB)       │
│              ↓                                          │
│        Application Gateway (L7 LB + SSL termination)   │
│              ↓                                          │
│          AKS Cluster                                    │
│          ├── FastAPI pods (3 replicas)                  │
│          ├── Celery worker pods                         │
│          └── Nginx ingress                              │
│                                                         │
│  Data Layer:                                            │
│  ├── Azure Database for PostgreSQL (Flexible Server)    │
│  ├── Azure Cache for Redis                              │
│  └── Azure Blob Storage (files, user uploads)          │
│                                                         │
│  Messaging:                                             │
│  └── Azure Service Bus (task queues)                   │
│                                                         │
│  Secrets: Azure Key Vault                               │
│  Identity: Managed Identity (no credentials in code)   │
│  Registry: Azure Container Registry                    │
│  CI/CD: Azure Pipelines or GitHub Actions              │
│  Monitoring: Azure Monitor + Application Insights      │
│  Logs: Log Analytics Workspace                          │
└─────────────────────────────────────────────────────────┘
```

---

## Terraform for Azure

```hcl
# main.tf
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~>3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = "fastapi-prod"
  location = "West India"
}

# PostgreSQL Flexible Server
resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "my-postgres-server"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = "16"
  administrator_login    = "myadmin"
  administrator_password = var.db_password
  storage_mb             = 32768
  sku_name               = "B_Standard_B1ms"
}

# AKS Cluster
resource "azurerm_kubernetes_cluster" "main" {
  name                = "my-aks-cluster"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  dns_prefix          = "myaks"

  default_node_pool {
    name       = "default"
    node_count = 2
    vm_size    = "Standard_B2s"
  }

  identity {
    type = "SystemAssigned"
  }
}
```

---

## Cost Estimation (Monthly — India region)

| Service | Tier | Approx Monthly Cost |
|---------|------|-------------------|
| Azure VM (B2s — 2CPU, 4GB) | Standard | ~$30–40 |
| App Service (B2 — 2CPU, 3.5GB) | Basic | ~$35 |
| AKS (2 × B2s nodes) | Standard | ~$60–80 |
| Azure Database for PostgreSQL (B1ms) | Burstable | ~$15 |
| Azure Cache for Redis (C0) | Basic | ~$20 |
| Azure Blob Storage (100GB) | LRS | ~$2 |
| Azure Service Bus (1M messages) | Basic | ~$0.05 |
| Azure Container Registry | Basic | ~$5 |

**Free tier available:** 12 months free for new accounts — includes B1s VM, 5GB Blob, 250GB SQL.

---

## Key Difference: Azure AD Roles vs RBAC

```
Azure RBAC    = controls who can access Azure resources (VMs, databases, storage)
Azure AD Roles = controls who can manage Azure AD itself (users, groups, apps)

Common mistake: thinking Azure AD "Global Admin" = full Azure access
Reality: Azure RBAC "Owner" = full resource access; Global Admin = AD management only
```

---

## Local Development with Azure Services (Azurite)

```bash
# Azurite = local Azure Storage emulator (like LocalStack for Azure)
npm install -g azurite
azurite --silent &

# Use in Python (same SDK, just different connection string)
from azure.storage.blob import BlobServiceClient

# Local emulator
client = BlobServiceClient.from_connection_string(
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
)
```
