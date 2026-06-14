# =============================================================================
# main.tf  --  Twin serverless stack, POORA infra ek hi code file me.
# =============================================================================
# KYA HAI YEH FILE (Hinglish):
#   Yeh wahi "saara console clicking" hai (L50-L53) jo Day 2 me hum hath se
#   karte the -- Lambda banao, IAM role do, S3 bucket banao, API Gateway khada
#   karo, CloudWatch log group set karo -- ab sab DECLARATIVE code me.
#
#   IMPERATIVE (purana, ClickOps) vs DECLARATIVE (Terraform):
#     - ClickOps = "pehle yeh banao, phir woh, phir us field me yeh type karo".
#       Ek hyphen galat (us-east-1 -> useast1) => "god help you" (L50).
#     - Terraform = tum sirf DESIRED END-STATE describe karte ho. Terraform khud
#       reality (state file) se diff nikaalta hai aur reconcile karta hai. Bilkul
#       Kubernetes manifests / Ansible-with-idempotency jaisa mental model.
#
#   DEPENDENCY GRAPH: Terraform resource references (e.g.
#   aws_iam_role.lambda_role.arn) se khud ek DAG banata hai aur SAHI ORDER me
#   create karta hai. Tumhe "pehle role, phir lambda" likhne ki zaroorat nahi --
#   reference dene se hi ordering aa jaati hai (jaise Make/Bazel ya DI container).
#
#   var.environment (dev/test/prod) HAR resource ke naam + tags me inject hota
#   hai -- isliye teeno environments ek hi AWS account me bina collision ke
#   parallel coexist karte hain (L54). Yahi "ek code, N environments" IaC power.
# =============================================================================


# -----------------------------------------------------------------------------
# terraform {} block -- provider VERSION PINNING.
# -----------------------------------------------------------------------------
# WHY: "~> 5.0" ka matlab ">=5.0, <6.0" -- yaani 5.x me koi bhi minor/patch chalega
# par 6.0 (jo breaking ho sakta hai) apne aap nahi aayega. Reproducible builds ka
# pehla rule: jo plugin/version aaj kaam kar raha hai, kal bhi wahi mile. (Ed ne
# isse `versions.tf` me alag rakha tha L51; hum simplicity ke liye yahin daal
# rahe -- Terraform waise bhi saari .tf files ko ek list me merge kar deta hai.)
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# -----------------------------------------------------------------------------
# provider "aws" -- konsa cloud, konsa region.
# -----------------------------------------------------------------------------
# WHY: provider = cloud vendor plugin (L50 ka core term). region var se aata hai
# taaki dev/prod alag region me jaa sake bina code badle. default_tags = har
# resource par automatically yeh tags lag jaate hain => cost-attribution +
# observability ("yeh resource kis env/project ka hai" filter karna easy).
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform" # taaki koi galti se console se na chhede
    }
  }
}

# -----------------------------------------------------------------------------
# locals -- ek baar compute karke baar-baar reuse.
# -----------------------------------------------------------------------------
# WHY: name_prefix = "twin-dev" / "twin-test" / "twin-prod" -- yeh ek hi jagah
# banta hai aur har resource isse use karta hai. DRY principle: agar naming
# scheme badalni ho to ek hi line badlo. (L51 me Ed ne isi prefix se environments
# separate kiye the: var.prefix -> twin-dev / twin-test / twin-prod.)
locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# -----------------------------------------------------------------------------
# data "aws_caller_identity" -- abhi konse AWS account me hain, uska account_id.
# -----------------------------------------------------------------------------
# WHY: `data` source = read-only lookup (kuch banata nahi, sirf info laata hai).
# S3 bucket names GLOBALLY unique hone chahiye (poori duniya me), isliye bucket
# naam me account_id suffix lagate hain => clash ka chance khatam (L51 pattern).
# NOTE: local plan/apply ke bina yeh resolve nahi hota -- isiliye humara Python
# helper sirf resources ko PARSE/summarize karta hai, terraform run nahi karta.
data "aws_caller_identity" "current" {}

# =============================================================================
# 1) IAM ROLE + POLICY  --  Lambda ko LEAST-PRIVILEGE permissions.
# =============================================================================
# WHY IAM ROLE: Lambda ko khud-ba-khud kuch karne ki permission nahi hoti. Use ek
# "role" assume karna padta hai jisme policies attached hoti hain. Yeh role hi
# decide karta hai Lambda S3/CloudWatch/Bedrock ko chhoo sakta hai ya nahi.
#
# LEAST PRIVILEGE: Ed ne L51 me convenience ke liye AmazonS3FullAccess +
# AmazonBedrockFullAccess (managed full-access policies) attach kiye the. Woh
# DEMO ke liye theek hai par PRODUCTION me khatarnak (full access = blast radius
# bada). Yahan hum jaan-bujhke ek SCOPED inline policy likh rahe hain: sirf
#   (a) CloudWatch Logs likhna, aur
#   (b) IS env ke memory bucket par get/put/list/delete -- aur kuch nahi.
# Yahi backend dev note ka asli production lesson hai.

# (a) assume-role policy: "kaun is role ko pehen sakta hai?" -> sirf Lambda service.
#     trust policy aur permission policy alag cheezein hain -- yeh trust hai.
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"] # sirf Lambda hi assume kar sake
    }
  }
}

resource "aws_iam_role" "lambda_role" {
  name               = "${local.name_prefix}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

# (b) permission policy: yeh role ASLI me kya-kya KAR sakta hai (least-privilege).
#     Resource ARNs ko bucket tak SCOPE kiya hai -- "*" nahi (security).
data "aws_iam_policy_document" "lambda_permissions" {
  # --- CloudWatch Logs: Lambda apne logs likh sake (warna observability zero) ---
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    # IS env ke log group tak hi scoped (sab logs par * nahi).
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }

  # --- S3 read/write: sirf IS env ke memory bucket par (conversation memory) ---
  statement {
    sid    = "S3MemoryReadWrite"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    # do ARNs chahiye: bucket khud (ListBucket ke liye) + uske andar ke objects.
    resources = [
      aws_s3_bucket.memory.arn,
      "${aws_s3_bucket.memory.arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda_inline" {
  name   = "${local.name_prefix}-lambda-policy"
  role   = aws_iam_role.lambda_role.id
  policy = data.aws_iam_policy_document.lambda_permissions.json
}

# =============================================================================
# 2) S3 BUCKET (memory)  --  conversation history persist karne ke liye.
# =============================================================================
# WHY: serverless me Lambda STATELESS hota hai -- har invocation fresh container,
# local disk ephemeral. Conversation/agent memory ko bahar persist karna padta
# hai => S3 (L42/L53: USE_S3=true, JSON blob per conversation). bucket naam:
#   twin-dev-memory-<accountId>  (env prefix + globally-unique account suffix).
resource "aws_s3_bucket" "memory" {
  bucket = "${local.name_prefix}-memory-${data.aws_caller_identity.current.account_id}"
}

# block_public_access: memory me user conversations hain -- yeh DATA hai, kabhi
# public nahi hona chahiye. Default-secure: chaaro public knobs band.
resource "aws_s3_bucket_public_access_block" "memory" {
  bucket                  = aws_s3_bucket.memory.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# versioning: galti se overwrite/delete hone par purana version recover ho sake.
# (Audit + safety; production memory bucket par sensible default.)
resource "aws_s3_bucket_versioning" "memory" {
  bucket = aws_s3_bucket.memory.id
  versioning_configuration {
    status = "Enabled"
  }
}

# =============================================================================
# 3) CLOUDWATCH LOG GROUP  --  Lambda ke logs ka ghar.
# =============================================================================
# WHY: Lambda by default ek log group bana leta hai, par usse EXPLICITLY declare
# karne ke do bade faayde: (1) retention set kar sakte ho (logs hamesha ke liye
# rakhna = paisa); (2) terraform destroy ise bhi clean kar dega (orphaned logs
# silent cost nahi banenge -- L55 teardown discipline). Naam ka format Lambda
# convention follow karta hai: /aws/lambda/<function-name>.
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name_prefix}-api"
  retention_in_days = var.log_retention_days # dev me chhota, prod me bada (tfvars)
}

# =============================================================================
# 4) LAMBDA FUNCTION  --  asli compute. Humara deployable handler.
# =============================================================================
# WHY: yeh wahi function hai jo API Gateway ke peeche chalta hai. Code ek ZIP se
# aata hai (humara Python helper banata hai build/lambda.zip). handler =
# "<file>.<function>" -- yaani Lambda kis file ki kaunsi function call kare.
# Ed ka convention "lambda_handler.handler" tha; hamare lab me handler
# lab4_terraform_iac.py me hai, isliye default var.lambda_handler =
# "lab4_terraform_iac.handler".
resource "aws_lambda_function" "api" {
  function_name = "${local.name_prefix}-api"

  # ZIP se deploy: filename + source_code_hash. hash isliye zaroori hai ki agar
  # zip badle to Terraform ko pata chale "code change hua, redeploy karo" (warna
  # wahi purana code chipka rehta). filebase64sha256 build-time par compute hota.
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  role          = aws_iam_role.lambda_role.arn # upar wali least-privilege role
  handler       = var.lambda_handler           # "<module>.<function>"
  runtime       = var.lambda_runtime           # e.g. python3.12
  architectures = ["x86_64"]                    # L48/L51: build-arch parity dhyaan
  timeout       = var.lambda_timeout            # var se (LLM calls slow ho sakti)
  memory_size   = var.lambda_memory_mb

  # ENVIRONMENT VARIABLES: code ko bina chhede config inject karna (12-factor).
  # USE_S3, memory bucket name, aur bedrock model id -- sab yahin wire hota hai.
  environment {
    variables = {
      ENVIRONMENT      = var.environment
      USE_S3           = "true"
      MEMORY_BUCKET    = aws_s3_bucket.memory.bucket
      BEDROCK_MODEL_ID = var.bedrock_model_id
    }
  }

  # depends_on: strictly zaroori NAHI (Terraform inline-policy/role/log-group ko
  # references se figure out kar leta -- L51 ka point). Par explicitly likhna
  # readability deta hai: "Lambda tab bane jab role-policy + log group ready ho".
  depends_on = [
    aws_iam_role_policy.lambda_inline,
    aws_cloudwatch_log_group.lambda,
  ]
}

# =============================================================================
# 5) API GATEWAY (HTTP API v2)  --  internet se Lambda tak front-door.
# =============================================================================
# WHY HTTP API (v2, not REST v1): sasta + simple + tezz. Browser/curl yahan
# request bhejta hai, API Gateway use Lambda ko proxy kar deta hai, response
# wapas. Yahi public endpoint frontend call karta hai (L43).

# (a) API container -- protocol HTTP.
resource "aws_apigatewayv2_api" "http" {
  name          = "${local.name_prefix}-http-api"
  protocol_type = "HTTP"

  # CORS: browser security. Sirf hamare frontend origin ko allow karo -- "*"
  # production me galat (koi bhi site teri API hit kar legi). dev me "*" chalega,
  # prod me CloudFront/custom-domain origin (L53/L54 ka CORS-per-env lesson).
  cors_configuration {
    allow_origins = var.cors_allow_origins
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type"]
  }
}

# (b) Integration -- "is API ko Lambda se jodo". AWS_PROXY = pura request event
#     ke roop me Lambda ko pass, aur Lambda ka {statusCode, body} response banta.
#     payload_format_version "2.0" => event me requestContext.http.method/path
#     aata hai (humara handler dono shapes -- v1 httpMethod aur v2 -- handle karta).
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

# (c) Route -- konsa path/method kis integration par jaaye. "$default" catch-all
#     => saari requests Lambda ko (app khud routing kare). Simplicity ke liye.
resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# (d) Stage -- deployed version ka URL segment. auto_deploy=true => route/integration
#     badalne par apne aap deploy. "$default" stage => URL me extra path nahi.
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
}

# (e) Permission -- API Gateway ko Lambda INVOKE karne ki ijaazat do. Bina iske
#     gateway 403/500 dega. source_arn se scope: sirf YEH api hi invoke kar sake.
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
