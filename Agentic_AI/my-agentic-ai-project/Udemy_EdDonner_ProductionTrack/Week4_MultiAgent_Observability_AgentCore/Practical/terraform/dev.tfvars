# =============================================================================
# dev.tfvars — DEV environment ke concrete values. `-var-file=dev.tfvars` se load.
# =============================================================================
# WHY .tfvars (na ki main.tf me hard-code): ek hi config alag environments ke liye
# (dev.tfvars / prod.tfvars). Real secrets (Aurora ARN/secret) yahan PLACEHOLDER hain —
# asli deploy me apne actual ARNs daalo, AUR is file ko .gitignore me rakho (secrets git me na jaayein).
#
# NOTE (Ed L100): aurora_cluster_arn / aurora_secret_arn ko BLANK ("") bhi chhod sakte ho —
# tab Terraform existing infra se data-source lookup karta. Yahan teaching ke liye explicit
# placeholder dikhaye hain taaki saaf dikhe Lambda ko exactly kya-kya chahiye.
# =============================================================================

region      = "us-east-1"
project     = "alex"
environment = "dev"
account_id  = "123456789012" # <-- apna 12-digit AWS account ID daalo

# --- Lambda packaging (lab packager ka output) ---
lambda_zip_path    = "../build/agent_lambda.zip"
lambda_memory_mb   = 512
lambda_timeout_s   = 60
log_retention_days = 14

# --- Aurora Serverless v2 (RDS Data API) — PLACEHOLDER, apne actual ARNs daalo ---
aurora_cluster_arn = "arn:aws:rds:us-east-1:123456789012:cluster:alex-aurora-dev"
aurora_secret_arn  = "arn:aws:secretsmanager:us-east-1:123456789012:secret:alex-aurora-creds-AbCdEf"
db_name            = "alex"

# --- Bedrock (LLM inference) ---
bedrock_model_id = "amazon.nova-pro-v1:0" # OSS 120B bhi try kar sakte ho
bedrock_region   = "us-west-2"

# --- API Gateway ---
cors_allow_origins = ["*"] # dev me sab; PROD me exact domain (e.g. ["https://app.alex.example"])
throttle_burst     = 20
throttle_rate      = 10
