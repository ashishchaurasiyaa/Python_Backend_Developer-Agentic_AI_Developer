# Azure Hands-On Lab

## Prerequisites
- Azure account (free tier: portal.azure.com — 12 months free)
- Azure CLI installed: `brew install azure-cli`
- Docker installed

---

## Lab 1 — Azure CLI Setup + First Resource

### Step 1: Login and explore
```bash
# Login (opens browser)
az login

# See your subscriptions
az account list --output table

# Set default subscription
az account set --subscription "<your-subscription-id>"

# See all locations
az account list-locations --output table | grep -i india
```

### Step 2: Create your first Resource Group
```bash
az group create \
  --name my-learning-rg \
  --location westindia

# Verify
az group show --name my-learning-rg --output table
```

---

## Lab 2 — Deploy FastAPI to Azure App Service

### Step 3: Create a simple FastAPI app
```python
# app/main.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello from Azure!", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy"}
```

```
# requirements.txt
fastapi
uvicorn[standard]
gunicorn
```

```
# startup.sh
gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

### Step 4: Deploy to App Service
```bash
# Create App Service Plan
az appservice plan create \
  --name my-learning-plan \
  --resource-group my-learning-rg \
  --sku F1 \           # F1 = Free tier
  --is-linux

# Create Web App
az webapp create \
  --resource-group my-learning-rg \
  --plan my-learning-plan \
  --name my-fastapi-$(date +%s) \    # unique name required globally
  --runtime "PYTHON|3.11"

# Get the app name you just created
APP_NAME=$(az webapp list --resource-group my-learning-rg --query "[0].name" -o tsv)

# Set startup command
az webapp config set \
  --resource-group my-learning-rg \
  --name $APP_NAME \
  --startup-file "gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000"

# Deploy (zip deploy)
zip -r app.zip app/ requirements.txt
az webapp deploy \
  --resource-group my-learning-rg \
  --name $APP_NAME \
  --src-path app.zip \
  --type zip

# Get URL
echo "App URL: https://$APP_NAME.azurewebsites.net"
curl https://$APP_NAME.azurewebsites.net/health
```

---

## Lab 3 — Azure Blob Storage

### Step 5: Create storage account and upload a file
```bash
# Create storage account (name must be globally unique, lowercase, 3-24 chars)
STORAGE_NAME="mystorage$(date +%s)"

az storage account create \
  --name $STORAGE_NAME \
  --resource-group my-learning-rg \
  --location westindia \
  --sku Standard_LRS

# Get connection string
CONN_STR=$(az storage account show-connection-string \
  --name $STORAGE_NAME \
  --resource-group my-learning-rg \
  --query connectionString -o tsv)

# Create container
az storage container create \
  --name uploads \
  --connection-string "$CONN_STR"

# Upload a file
echo "Hello Azure Storage" > test.txt
az storage blob upload \
  --container-name uploads \
  --name test.txt \
  --file test.txt \
  --connection-string "$CONN_STR"

# List blobs
az storage blob list \
  --container-name uploads \
  --connection-string "$CONN_STR" \
  --output table

# Download blob
az storage blob download \
  --container-name uploads \
  --name test.txt \
  --file downloaded.txt \
  --connection-string "$CONN_STR"

cat downloaded.txt
```

### Step 6: Generate SAS URL (pre-signed link)
```bash
# Generate SAS URL valid for 1 hour
END_TIME=$(date -u -d "1 hour" '+%Y-%m-%dT%H:%MZ' 2>/dev/null || \
  date -u -v+1H '+%Y-%m-%dT%H:%MZ')

SAS_TOKEN=$(az storage blob generate-sas \
  --account-name $STORAGE_NAME \
  --container-name uploads \
  --name test.txt \
  --permissions r \
  --expiry $END_TIME \
  --connection-string "$CONN_STR" \
  --output tsv)

echo "SAS URL: https://$STORAGE_NAME.blob.core.windows.net/uploads/test.txt?$SAS_TOKEN"
# Anyone can download this URL for 1 hour
```

---

## Lab 4 — Azure Container Registry + Docker

### Step 7: Push a Docker image to ACR
```bash
# Create Container Registry
ACR_NAME="myacr$(date +%s)"

az acr create \
  --resource-group my-learning-rg \
  --name $ACR_NAME \
  --sku Basic

# Login to ACR
az acr login --name $ACR_NAME

# Build and push image
cat > Dockerfile << 'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

docker build -t $ACR_NAME.azurecr.io/fastapi-app:v1 .
docker push $ACR_NAME.azurecr.io/fastapi-app:v1

# List images in ACR
az acr repository list --name $ACR_NAME --output table
az acr repository show-tags --name $ACR_NAME --repository fastapi-app --output table
```

---

## Lab 5 — Azure Key Vault (Secrets Management)

### Step 8: Store and retrieve secrets
```bash
# Create Key Vault
az keyvault create \
  --name mykeyvault-$(date +%s) \
  --resource-group my-learning-rg \
  --location westindia

VAULT_NAME=$(az keyvault list --resource-group my-learning-rg --query "[0].name" -o tsv)

# Store secrets
az keyvault secret set \
  --vault-name $VAULT_NAME \
  --name "database-password" \
  --value "MySecurePassword123!"

az keyvault secret set \
  --vault-name $VAULT_NAME \
  --name "openai-api-key" \
  --value "sk-test-placeholder"

# Retrieve secret
az keyvault secret show \
  --vault-name $VAULT_NAME \
  --name "database-password" \
  --query value -o tsv

# List secrets
az keyvault secret list --vault-name $VAULT_NAME --output table
```

### Step 9: Access Key Vault from Python
```python
# pip install azure-identity azure-keyvault-secrets

from azure.identity import AzureCliCredential
from azure.keyvault.secrets import SecretClient

# Uses your az login credentials locally
credential = AzureCliCredential()

vault_url = f"https://{vault_name}.vault.azure.net/"
client = SecretClient(vault_url=vault_url, credential=credential)

secret = client.get_secret("database-password")
print(f"Secret: {secret.value}")
```

---

## Lab 6 — Azure Monitor + Logs

### Step 10: Enable diagnostics on App Service
```bash
# Enable logging for your App Service
az webapp log config \
  --resource-group my-learning-rg \
  --name $APP_NAME \
  --docker-container-logging filesystem \
  --level information

# Stream live logs
az webapp log tail \
  --resource-group my-learning-rg \
  --name $APP_NAME

# Download logs
az webapp log download \
  --resource-group my-learning-rg \
  --name $APP_NAME \
  --log-file webapp_logs.zip
```

---

## Lab 7 — Cleanup (avoid charges)

```bash
# Delete the entire resource group (deletes everything inside)
az group delete --name my-learning-rg --yes --no-wait

echo "All Azure resources deleted"
```

---

## Checklist — What You Should Be Able to Do Now

- [ ] Login to Azure CLI and create Resource Groups
- [ ] Deploy a Python/FastAPI app to Azure App Service
- [ ] Create a Storage Account and upload/download blobs
- [ ] Generate SAS URLs for temporary access
- [ ] Build and push Docker images to Azure Container Registry
- [ ] Store and retrieve secrets from Azure Key Vault
- [ ] View and stream App Service logs
- [ ] Clean up resources to avoid charges
