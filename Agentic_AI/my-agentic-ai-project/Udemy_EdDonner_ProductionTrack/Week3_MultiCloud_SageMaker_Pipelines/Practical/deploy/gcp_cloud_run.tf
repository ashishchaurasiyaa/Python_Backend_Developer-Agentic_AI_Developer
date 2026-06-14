# ============================================================================
# gcp_cloud_run.tf — deploy the SAME image to GCP Cloud Run
# ============================================================================
# Yeh wahi container (deploy/Dockerfile se built image) GCP par chalata hai (L70/L72/L73).
# azure_container_app.tf ke saath side-by-side dekho: provider alag (google vs azurerm),
# par WORKFLOW + intent IDENTICAL — Terraform dono clouds ko ek-jaisa abstract karta hai
# (L72/L73). Same image, sirf alag .tf => "build once, deploy anywhere".
#
# Workflow (Ed, L72): gcloud auth login -> set project -> application-default login ->
#   set-quota-project -> configure-docker -> terraform init -> workspace select gcp ->
#   terraform plan -> terraform apply -> (cleanup) terraform destroy (L73 ALWAYS).
#
# Run:
#   terraform init
#   terraform workspace new gcp     # pehli baar
#   terraform workspace select gcp
#   export TF_VAR_project_id=<your-gcp-project-id>   # L72 TF_VAR_ convention
#   terraform plan  -var "image=<region>-docker.pkg.dev/<proj>/<repo>/multicloud-agent:latest" -var "groq_api_key=$GROQ_API_KEY"
#   terraform apply -var "image=..." -var "groq_api_key=$GROQ_API_KEY"

# ----------------------------------------------------------------------------
# providers — google (L72). Cloud-agnostic Terraform: sirf yeh block azurerm se alag.
# ----------------------------------------------------------------------------
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# provider auth: ADC (Application Default Credentials) — `gcloud auth application-default
# login` se aati hain, Terraform AUTOMATICALLY uthata hai (L72). project + region yahan.
provider "google" {
  project = var.project_id
  region  = var.region
}

# ----------------------------------------------------------------------------
# variables — config bahar se (12-factor), Azure file ke parallel (L72).
# ----------------------------------------------------------------------------
variable "project_id" {
  description = "GCP Project ID — globally unique, letter-for-letter sahi (L72). TF_VAR_project_id se aata hai."
  type        = string
}

variable "region" {
  description = "GCP region — Cloud Run service yahan deploy hoga (L72 us-central1 jaisa)."
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run service ka naam (Azure ke app_name ke parallel)."
  type        = string
  default     = "multicloud-agent"
}

variable "image" {
  description = "Container image (Artifact Registry/GCR path). YAHI wahi image jo Azure"
  type        = string # file me bhi point hoti hai — ek artifact, do clouds (L73 parity).
}

variable "groq_api_key" {
  description = "LLM key — Cloud Run env var ke roop me inject (image me bake NAHI, L66)."
  type        = string
  sensitive   = true # plan/apply output me mask (Azure file ke parallel).
  default     = ""
}

# ----------------------------------------------------------------------------
# THE Cloud Run service — humara image yahan LIVE (L72 google_cloud_run_v2_service).
# ----------------------------------------------------------------------------
# Cloud Run = container-as-a-service (L73 sweet-spot). Ek image do, GCP on-demand chalata
# hai, traffic par auto-scale, idle par scale-to-zero. Azure Container App ka GCP bhai.
resource "google_cloud_run_v2_service" "app" {
  name     = var.service_name
  location = var.region
  # Public service ko bina org-policy block ke allow karta hai (ADC project setup ke saath).
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    # scale-to-zero (L73): min=0 => idle par $0, max=1 => demo cap.
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = var.image # <-- SAME image jo Dockerfile se bani (Azure file me bhi yahi var)

      # container ka listening port = 8000 (uvicorn 0.0.0.0:8000; Dockerfile EXPOSE 8000;
      # Azure ingress target_port=8000) — port parity teeno jagah.
      ports {
        container_port = 8000
      }

      # --- resources: L72 ka MEMORY GOTCHA --------------------------------
      # Default chhota ho sakta hai; agar app startup par memory spike kare (Ed ke
      # Semgrep MCP server jaisa) to silently OOM-kill ho jaati hai. Isliye explicit
      # tune karo — sirf default par bharosa mat karo (L72/L73 production lesson).
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      # CLOUD label => /health aur /chat response me "cloud":"gcp" dikhega. Image SAME,
      # sirf yeh env var alag (Azure file me CLOUD=azure) — build-once-run-anywhere proof.
      env {
        name  = "CLOUD"
        value = "gcp"
      }
      # API key env var se (app ke andar os.getenv("GROQ_API_KEY") ise padhta).
      env {
        name  = "GROQ_API_KEY"
        value = var.groq_api_key
      }
    }
  }
}

# ----------------------------------------------------------------------------
# IAM invoker — public access (L72: roles/run.invoker, member allUsers).
# ----------------------------------------------------------------------------
# Cloud Run default PRIVATE hota hai. Public banane ke liye allUsers ko run.invoker do.
# (Azure me iska analog: ingress external_enabled=true. Concept same: "publicly callable".)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = google_cloud_run_v2_service.app.project
  location = google_cloud_run_v2_service.app.location
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ----------------------------------------------------------------------------
# outputs — apply ke baad live URL (Azure file ke parallel, L72).
# ----------------------------------------------------------------------------
output "service_url" {
  description = "Live HTTPS URL (run.app). Yahan /health + /chat hit karo (Azure ke parallel)."
  value       = google_cloud_run_v2_service.app.uri
}

output "project_id" {
  description = "GCP project — cleanup/verify ke liye (`terraform destroy`, L73 ALWAYS)."
  value       = var.project_id
}
