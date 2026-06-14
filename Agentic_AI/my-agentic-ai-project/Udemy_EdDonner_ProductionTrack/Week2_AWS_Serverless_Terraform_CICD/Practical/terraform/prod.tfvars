# =============================================================================
# prod.tfvars  --  PRODUCTION environment ke liye variable VALUES (overrides).
# =============================================================================
# WHY (Hinglish): same main.tf, par prod-grade values. prod = quality + safety.
# Behtar model (Nova pro -- L54), generous timeout/memory, lambi log-retention
# (audit/compliance), aur CORS LOCKED to apna asli frontend origin (security --
# "*" production me galat, koi bhi site teri API hit kar legi). Run karo:
#   terraform apply -var-file=prod.tfvars
#
# IMPORTANT (L54 best practice): prod ke liye ALAG IAM user/role/account use
# karo (permission isolation) -- taaki ek galat command prod ko na touch kare.
# =============================================================================

environment        = "prod"
project_name       = "twin"
region             = "us-east-1"

bedrock_model_id   = "amazon.nova-pro-v1:0"     # prod: behtar quality (still cheap ~Haiku)
lambda_timeout     = 60
lambda_memory_mb   = 512                          # prod: thoda zyada => tezz cold-start/CPU
log_retention_days = 90                           # prod: audit ke liye logs lambe rakho

# CORS: SIRF apna frontend origin -- "*" mat rakhna. Apne asli CloudFront/custom
# domain se replace karo (placeholder neeche example hai).
cors_allow_origins = ["https://twin.example.com"]
