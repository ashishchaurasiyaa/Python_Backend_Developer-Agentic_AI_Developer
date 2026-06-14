# =============================================================================
# variables.tf  --  saare "settings/knobs" jo deployment ko control karte hain.
# =============================================================================
# WHY (Hinglish): variables.tf sirf variables DECLARE karta hai (naam + type +
# optional default). Actual VALUES tfvars files (dev.tfvars / prod.tfvars) se
# aati hain. Yeh bilkul wahi pattern hai jo backend me hum settings.py + .env se
# karte hain: CODE ek hi rehta hai, CONFIG environment se aata hai (12-factor).
# Isliye same main.tf se dev, test, prod -- teeno ban jaate hain (L52/L54).
# =============================================================================

variable "region" {
  description = "AWS region jahan sab deploy hoga (e.g. us-east-1)."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project ka short naam -- resource naming ka prefix banata hai."
  type        = string
  default     = "twin"
}

variable "environment" {
  description = "dev / test / prod -- har resource ke naam+tags me inject hota hai, isi se environments isolate hote hain."
  type        = string
  default     = "dev"

  # validation: galat env (typo) ko APPLY se PEHLE pakdo -- plan hi fail ho jaaye.
  # Yahi "ek hyphen galat = god help you" (L50) ke against guardrail hai.
  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "environment sirf dev / test / prod me se ek hona chahiye."
  }
}

variable "lambda_zip_path" {
  description = "Lambda deployment ZIP ka path (humara Python helper build/lambda.zip banata hai)."
  type        = string
  default     = "../build/lambda.zip"
}

variable "lambda_handler" {
  description = "Lambda entrypoint '<module>.<function>'. Default lab4_terraform_iac.handler (self-contained, self-demo me bhi chalta). Lab1 ka handler deploy karna ho to 'lab1_lambda_handler_apigw.handler' set karo + us file ko zip karo (helper --build us file par)."
  type        = string
  default     = "lab4_terraform_iac.handler"
}

variable "lambda_runtime" {
  description = "Lambda Python runtime version."
  type        = string
  default     = "python3.12"
}

variable "lambda_timeout" {
  description = "Lambda timeout (seconds). LLM calls slow ho sakti hain isliye thoda generous."
  type        = number
  default     = 60
}

variable "lambda_memory_mb" {
  description = "Lambda memory (MB). Memory zyada => CPU bhi zyada (AWS coupled) => tezz, par mehenga."
  type        = number
  default     = 256
}

variable "bedrock_model_id" {
  description = "Bedrock model id. dev/test sasta (Nova micro/lite), prod behtar (Nova pro). L54."
  type        = string
  default     = "amazon.nova-micro-v1:0"
}

variable "log_retention_days" {
  description = "CloudWatch logs kitne din rakhne hain. dev me kam (cost), prod me zyada (audit)."
  type        = number
  default     = 7
}

variable "cors_allow_origins" {
  description = "CORS allowed origins. dev me '*' theek; prod me sirf apna frontend domain (security)."
  type        = list(string)
  default     = ["*"]
}
