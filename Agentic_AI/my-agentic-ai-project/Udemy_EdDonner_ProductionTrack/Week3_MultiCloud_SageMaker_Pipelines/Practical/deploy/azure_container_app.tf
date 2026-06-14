# ============================================================================
# azure_container_app.tf — deploy the SAME image to Azure Container Apps (ACA)
# ============================================================================
# Yeh wahi container (deploy/Dockerfile se built image) Azure par chalata hai (L68/L69).
# Workflow (Ed, L68): az login -> register resource providers -> terraform init ->
#   terraform plan -> terraform apply -> (cleanup) terraform destroy.
# GCP wale gcp_cloud_run.tf ke saath ise side-by-side dekho: provider block alag
# (azurerm vs google) par WORKFLOW + intent IDENTICAL = Terraform ki portability (L72/L73).
#
# Run (is folder me azure ka apna workspace rakho — L68):
#   terraform init
#   terraform workspace new azure   # pehli baar
#   terraform workspace select azure
#   terraform plan  -var "image=<acr-login-server>/multicloud-agent:latest" -var "groq_api_key=$GROQ_API_KEY"
#   terraform apply -var "image=..." -var "groq_api_key=$GROQ_API_KEY"

# ----------------------------------------------------------------------------
# providers — azurerm (L68). features {} block azurerm ke liye MANDATORY hai.
# ----------------------------------------------------------------------------
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# provider auth: `az login` ki credentials (L67/L68) automatically uthi jaati hain —
# secrets yahan hardcode NAHI. features {} = azurerm ka required empty config block.
provider "azurerm" {
  features {}
}

# ----------------------------------------------------------------------------
# variables — config bahar se aata hai (12-factor), code se nahi (L68).
# ----------------------------------------------------------------------------
variable "location" {
  description = "Azure region — sab resources same region me (L67 region consistency)."
  type        = string
  default     = "East US"
}

variable "resource_group_name" {
  description = "Resource Group ka naam (L67: cyber-analyzer-rg jaisa logical grouping)."
  type        = string
  default     = "multicloud-agent-rg"
}

variable "app_name" {
  description = "Container App ka naam (Azure me dns-safe, lowercase)."
  type        = string
  default     = "multicloud-agent"
}

variable "image" {
  description = "Container image reference (ACR login-server/multicloud-agent:tag). YAHI"
  type        = string # wahi image jo deploy/Dockerfile se bani — GCP file me bhi yahi.
}

variable "groq_api_key" {
  description = "LLM key — container me env var ke roop me inject (image me bake NAHI, L66)."
  type        = string
  sensitive   = true # plan/apply output me mask (L68 secrets handling).
  default     = ""
}

# ----------------------------------------------------------------------------
# resource group — Azure me har resource kisi RG me hota hai (L67 mandatory).
# ----------------------------------------------------------------------------
# RG = ek folder-jaisa logical grouping; poora environment ek RG me => `terraform destroy`
# se ek saath sab cleanup (L67/L69 ka "empty resource group reh jaata hai" wala point).
resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

# ----------------------------------------------------------------------------
# log analytics workspace — ACA environment ko logs ke liye chahiye (L68).
# ----------------------------------------------------------------------------
# Container Apps Environment apne logs yahan bhejta hai; L69 ka "Log Stream" / KQL isi
# workspace se aata hai. PerGB2018 = pay-per-GB ingested (chhota demo => negligible).
resource "azurerm_log_analytics_workspace" "logs" {
  name                = "${var.app_name}-logs"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# ----------------------------------------------------------------------------
# container app ENVIRONMENT — containers ke liye shared runtime/boundary (L68/L69).
# ----------------------------------------------------------------------------
# "Environment" = ek logical isolation boundary jisme ek-ya-zyada container apps chalte
# hain (networking + logging shared). GCP me iska koi direct exact analog nahi (Cloud Run
# service standalone hota), par concept: managed serverless container platform ka workspace.
resource "azurerm_container_app_environment" "env" {
  name                       = "${var.app_name}-env"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
}

# ----------------------------------------------------------------------------
# THE container app — humara image yahan LIVE hota hai (L69 main resource).
# ----------------------------------------------------------------------------
# Yeh wo resource hai jis par app azurecontainerapps.io URL par chalti hai (L69).
resource "azurerm_container_app" "app" {
  name                         = var.app_name
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  # Single: ek time par ek active revision (rolling deploy ke liye Multiple bhi hota hai).
  revision_mode = "Single"

  # --- secret: LLM key ko ACA secret store me rakho, env var se reference ----
  # Secret image me bake NAHI hoti (L66) — runtime par container ke andar inject.
  secret {
    name  = "groq-api-key"
    value = var.groq_api_key
  }

  template {
    # min=0 => scale-to-zero (idle par $0, CaaS ka core benefit, L73). max=1 => demo cap.
    min_replicas = 0
    max_replicas = 1

    container {
      name   = var.app_name
      image  = var.image # <-- SAME image jo Dockerfile se bani (GCP file me bhi yahi var)
      cpu    = 0.5       # vCPU (ACA consumption units). Bada workload ho to badhao (L72 memory gotcha).
      memory = "1Gi"     # RAM. Default chhota ho sakta hai — apni app ke footprint hisaab se tune.

      # CLOUD label => /health aur /chat response me "cloud":"azure" dikhega. Image SAME,
      # sirf yeh env var alag (GCP file me CLOUD=gcp) — yahi build-once-run-anywhere proof.
      env {
        name  = "CLOUD"
        value = "azure"
      }
      # API key secret se (plaintext nahi). App ke andar os.getenv("GROQ_API_KEY") ise padhta.
      env {
        name        = "GROQ_API_KEY"
        secret_name = "groq-api-key"
      }
    }
  }

  # --- ingress — bahar se traffic port 8000 par (Dockerfile EXPOSE 8000 ke saath match) -
  # external_enabled=true => public URL (L69 azurecontainerapps.io). target_port=8000 =
  # container ka listening port (uvicorn 0.0.0.0:8000). GCP file me bhi 8000 — port parity.
  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}

# ----------------------------------------------------------------------------
# outputs — apply ke baad live URL (L68 outputs main.tf me hi squash, alag file nahi).
# ----------------------------------------------------------------------------
output "app_url" {
  description = "Live HTTPS URL (azurecontainerapps.io). Yahan /health + /chat hit karo."
  value       = "https://${azurerm_container_app.app.ingress[0].fqdn}"
}

output "resource_group" {
  description = "RG naam — cleanup ke liye (`terraform destroy` se andar sab delete)."
  value       = azurerm_resource_group.rg.name
}
