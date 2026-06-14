# =============================================================================
# dev.tfvars  --  DEVELOPMENT environment ke liye variable VALUES.
# =============================================================================
# WHY (Hinglish): same main.tf, alag values. dev = sasta + tezz iterate. Sasta
# model (Nova micro), chhota timeout/memory, kam log-retention, CORS "*" (local
# testing easy). Run karo:  terraform apply -var-file=dev.tfvars  (L53/L54).
#
# NOTE: real project me *.tfvars ko gitignore karte hain agar secrets ho (L51),
# par yeh waali sirf non-secret config hai, isliye repo me rakhna theek hai.
# =============================================================================

environment        = "dev"
project_name       = "twin"
region             = "us-east-1"

bedrock_model_id   = "amazon.nova-micro-v1:0" # sabse sasta -- dev iterate ke liye kaafi
lambda_timeout     = 30
lambda_memory_mb   = 256
log_retention_days = 7                          # dev logs lambe nahi rakhne (cost)

cors_allow_origins = ["*"]                      # dev: local/anywhere se test -- "*" ok
