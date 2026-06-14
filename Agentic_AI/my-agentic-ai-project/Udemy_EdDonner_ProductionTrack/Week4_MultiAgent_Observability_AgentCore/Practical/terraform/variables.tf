# =============================================================================
# variables.tf — saare INPUTS (kya bahar se aata hai). dev.tfvars inhe bharta hai.
# =============================================================================
# WHY variables (hard-code nahi): ek hi main.tf ko dev/stage/prod me reuse kar sakein —
# sirf alag .tfvars file. Aur secrets (Aurora ARN/secret) git me na jaayein, runtime par aayein.
# Har var ka `type` + `description` + (jahan safe) `default` — IaC documentation ka hissa.
# =============================================================================

variable "region" {
  type        = string
  description = "AWS region jahan Lambda + API Gateway banenge (e.g. us-east-1)."
  default     = "us-east-1"
}

variable "project" {
  type        = string
  description = "Naming prefix — saare resources is se prefix honge (e.g. alex => alex-planner)."
  default     = "alex"
}

variable "environment" {
  type        = string
  description = "Deploy environment label (dev/stage/prod) — Lambda env var + tagging ke liye."
  default     = "dev"
}

variable "account_id" {
  type        = string
  description = "Tumhara 12-digit AWS account ID — CloudWatch log ARN scope karne ke liye."
  # default jaanboojh ke NAHI — galat account par deploy se bachne ke liye explicit maango.
}

# --- Lambda packaging -------------------------------------------------------
variable "lambda_zip_path" {
  type        = string
  description = "Deployment zip ka path (lab packager ka output: build/agent_lambda.zip)."
  default     = "../build/agent_lambda.zip"
}

variable "lambda_memory_mb" {
  type        = number
  description = "Lambda memory (MB). Lambda me memory se CPU bhi scale hoti — agent ke liye thoda generous."
  default     = 512
}

variable "lambda_timeout_s" {
  type        = number
  description = "Lambda timeout (seconds). Multi-agent orchestration slow — par <= 900 (Lambda max)."
  default     = 60
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention (din). forever rakhna mehnga + compliance risk."
  default     = 14
}

# --- Aurora (DB layer — RDS Data API) ---------------------------------------
# Ed L100: yeh BLANK chhod sakte ho aur Terraform existing infra se lookup kar leta;
# yahan hum explicit var rakhte (teaching ke liye saaf dikhe Lambda ko kya chahiye).
variable "aurora_cluster_arn" {
  type        = string
  description = "Aurora Serverless v2 cluster ka ARN (RDS Data API target). IAM isi par scope hota."
}

variable "aurora_secret_arn" {
  type        = string
  description = "Aurora DB creds ka Secrets Manager ARN (RDS Data API isse creds leta)."
}

variable "db_name" {
  type        = string
  description = "Aurora database ka naam (e.g. alex)."
  default     = "alex"
}

# --- Bedrock (LLM inference) ------------------------------------------------
variable "bedrock_model_id" {
  type        = string
  description = "Bedrock model id agent inference ke liye (Ed: amazon.nova-pro-v1:0 ya OSS 120B)."
  default     = "amazon.nova-pro-v1:0"
}

variable "bedrock_region" {
  type        = string
  description = "Bedrock region — aksar inference ke liye alag (Ed: us-west-2)."
  default     = "us-west-2"
}

# --- API Gateway ------------------------------------------------------------
variable "cors_allow_origins" {
  type        = list(string)
  description = "CORS allowed origins. dev me ['*'], prod me exact frontend domain (security)."
  default     = ["*"]
}

variable "throttle_burst" {
  type        = number
  description = "API GW burst limit — ek spike me max concurrent requests (abuse/cost brake)."
  default     = 20
}

variable "throttle_rate" {
  type        = number
  description = "API GW steady-state rate limit (req/sec)."
  default     = 10
}
