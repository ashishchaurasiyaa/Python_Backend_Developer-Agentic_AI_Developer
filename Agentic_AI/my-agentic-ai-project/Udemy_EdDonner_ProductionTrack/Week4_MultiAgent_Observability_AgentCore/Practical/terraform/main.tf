# =============================================================================
# main.tf — ALEX multi-agent "planner" Lambda ko API Gateway ke peeche deploy karna (IaC)
# =============================================================================
# Yeh wahi infra hai jo Ed L100 (6_agents) + L105 (7-front-end / api) me banata hai, par
# ek SINGLE agent-orchestrator (planner) ke liye SLIM kiya hua taaki teaching clear rahe.
#
# KYA BAN RAHA HAI (resource map — lab .py isi file ko regex se parse karke list karta hai):
#   - aws_iam_role               : Lambda ki execution identity (kaun ban ke chalega)
#   - aws_iam_role_policy        : us identity ko kya-kya karne ki permission (rds-data + bedrock + logs)
#   - aws_cloudwatch_log_group   : Lambda ke logs ka ghar (retention ke saath)
#   - aws_lambda_function        : planner orchestrator ka code (zip se) — API ka dimaag
#   - aws_apigatewayv2_api        : HTTP front-door (POST /plan yahan aata hai)
#   - aws_apigatewayv2_integration: API GW -> Lambda ko jodne wala "proxy" pipe
#   - aws_apigatewayv2_route      : "POST /plan" route ko integration par bhejo
#   - aws_apigatewayv2_stage      : deployable stage (auto-deploy on) — actual URL yahin se
#   - aws_lambda_permission       : API GW ko Lambda invoke karne ki ijaazat (warna 403)
#
# IMPORTANT (L104 ka sabak): yeh HCL ek LLM bhi likh sakta hai — par deploy se PEHLE
# human review + plan + tests MUST. IaC me ek galat IAM policy = production security hole.
# =============================================================================

# -----------------------------------------------------------------------------
# terraform block — Terraform ko bolo kaunsa provider chahiye + minimum version.
# WHY pin: bina version pin ke ek din provider upgrade tumhara plan toad sakta hai
# (reproducible builds ke liye version-lock karte hain — IaC ki neenv).
# -----------------------------------------------------------------------------
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0" # 5.x ke andar koi bhi minor — 6.0 jump auto nahi hoga
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0" # local zip ko data source se reference karne ke liye (optional path)
    }
  }
}

# -----------------------------------------------------------------------------
# aws provider — region var se aata hai. Creds yahan HARD-CODE NAHI karte;
# Terraform AWS_PROFILE / env creds / SSO se khud uthata hai (secrets git me na jaayein).
# -----------------------------------------------------------------------------
provider "aws" {
  region = var.region
}

# -----------------------------------------------------------------------------
# locals — baar-baar use hone wale derived naam ek jagah. Naming consistency =
# easy CloudWatch filtering + easy teardown (sab "alex-planner-*" prefix se).
# -----------------------------------------------------------------------------
locals {
  function_name = "${var.project}-planner" # e.g. alex-planner
  log_group     = "/aws/lambda/${var.project}-planner"
}

# =============================================================================
# IAM — Lambda ki IDENTITY + PERMISSIONS
# =============================================================================
# Do alag cheezein (aksar confuse hoti hain):
#   1) assume_role_policy  = "KAUN is role ko pehan sakta hai?"  -> sirf lambda.amazonaws.com
#   2) role_policy (inline) = "yeh role pehan ke kya kar sakta hai?" -> rds-data + bedrock + logs
# Least-privilege: sirf wahi actions jo planner ko chahiye — na ek zyada.
# -----------------------------------------------------------------------------
resource "aws_iam_role" "planner_exec" {
  name = "${var.project}-planner-exec-role"

  # Trust policy: sirf Lambda service is role ko assume kar sakti hai.
  # (Yeh "kaun" wala sawal — galti se "*" likha to koi bhi role hijack kar le.)
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = { Project = var.project, ManagedBy = "terraform" }
}

# Inline policy — planner ko teen cheezein chahiye:
#   (a) rds-data:*  -> Aurora Serverless ko RDS Data API se query/exec (DB layer)
#   (b) bedrock:InvokeModel -> agent ko LLM inference (Nova/Claude on Bedrock)
#   (c) logs:*      -> CloudWatch me apne logs likhna (warna kuch dikhega hi nahi)
# secretsmanager:GetSecretValue bhi — kyunki RDS Data API DB creds ek secret ARN se leta hai.
resource "aws_iam_role_policy" "planner_perms" {
  name = "${var.project}-planner-perms"
  role = aws_iam_role.planner_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # (a) Aurora data layer — RDS Data API (HTTP, no persistent connection pool).
        # Resource ko specific cluster ARN par baandha (var se) — "*" nahi (least-privilege).
        Sid    = "AuroraDataApi"
        Effect = "Allow"
        Action = [
          "rds-data:ExecuteStatement",
          "rds-data:BatchExecuteStatement",
          "rds-data:BeginTransaction",
          "rds-data:CommitTransaction",
          "rds-data:RollbackTransaction"
        ]
        Resource = var.aurora_cluster_arn
      },
      {
        # DB creds ek Secrets Manager secret me hote hain; Data API ko padhna padta hai.
        Sid      = "AuroraSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.aurora_secret_arn
      },
      {
        # (b) Bedrock inference — agent ka LLM. InvokeModel + streaming variant.
        # Resource "*" yahan thoda loose hai; prod me specific model ARN par baandho.
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      },
      {
        # (c) CloudWatch logs — log group/stream banao + events likho.
        # Bina is permission ke Lambda chalega par observability ZERO (debug impossible).
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:*"
      }
    ]
  })
}

# =============================================================================
# CloudWatch Log Group — Lambda ke logs ka explicit ghar
# =============================================================================
# WHY explicit (Lambda khud bana leta hai): explicit banane se hum RETENTION control
# kar sakte (warna logs forever rehte = paisa + compliance issue). Aur naam predictable
# rehta /aws/lambda/<function> — Lambda isi naam ko dhundta hai, isliye match zaroori.
resource "aws_cloudwatch_log_group" "planner_logs" {
  name              = local.log_group
  retention_in_days = var.log_retention_days # e.g. 14 — itna kaafi debugging ke liye, sasta
  tags              = { Project = var.project, ManagedBy = "terraform" }
}

# =============================================================================
# Lambda function — planner orchestrator (API ka dimaag)
# =============================================================================
# handler = "<module>.<function>" => "agent_lambda.handler" (hamari lab .py ka def handler).
# filename = packager ka banaya zip (build/agent_lambda.zip). source_code_hash se Terraform
# ko pata chalta hai zip badla ya nahi — badla to redeploy (warna stale code reh jaata).
resource "aws_lambda_function" "planner" {
  function_name = local.function_name
  role          = aws_iam_role.planner_exec.arn

  # --- packaging (L100/L105): zip Docker-Linux env me banta hai taaki native deps
  # (pydantic-core, etc.) Amazon Linux par chalein. filename = lab packager ka output. ---
  filename         = var.lambda_zip_path                  # build/agent_lambda.zip
  source_code_hash = filebase64sha256(var.lambda_zip_path) # zip change detection
  handler          = "agent_lambda.handler"               # module.function (def handler)
  runtime          = "python3.12"                         # repo requires-python >=3.12
  architectures    = ["arm64"]                            # Graviton = sasta + tez (x86 bhi OK)

  memory_size = var.lambda_memory_mb # zyada memory = zyada CPU bhi (Lambda me linked)
  timeout     = var.lambda_timeout_s # multi-agent orchestration slow ho sakta — generous

  # --- environment: agent ko runtime config. Secrets yahan PLAIN NAHI (ARN reference) ---
  # planner ko Aurora kaunsa cluster + secret, kaunsa Bedrock model/region — sab yahan se.
  environment {
    variables = {
      DB_CLUSTER_ARN  = var.aurora_cluster_arn # RDS Data API target (lab isi env ko padhta)
      DB_SECRET_ARN   = var.aurora_secret_arn  # DB creds secret
      DB_NAME         = var.db_name
      BEDROCK_MODEL   = var.bedrock_model_id # e.g. amazon.nova-pro-v1:0
      BEDROCK_REGION  = var.bedrock_region   # Bedrock alag region me ho sakta (us-west-2)
      LOG_LEVEL       = "INFO"
      ALEX_DEPLOY_ENV = var.environment # dev/stage/prod — code me branch karne ke liye
    }
  }

  # Log group pehle ban jaaye phir Lambda — warna race (Lambda apna default group bana de).
  depends_on = [
    aws_iam_role_policy.planner_perms,
    aws_cloudwatch_log_group.planner_logs
  ]

  tags = { Project = var.project, ManagedBy = "terraform" }
}

# =============================================================================
# API Gateway v2 (HTTP API) — POST /plan ka front-door
# =============================================================================
# v2 (HTTP API) chuna, na ki v1 (REST) — HTTP API sasta + simple + fast, aur "proxy"
# integration se pura request Lambda ko event ban ke milta hai (lab ka handler isi shape
# ka event expect karta: event["body"], event["requestContext"]["http"]["method"]...).
resource "aws_apigatewayv2_api" "alex_api" {
  name          = "${var.project}-api"
  protocol_type = "HTTP"
  description   = "ALEX planner orchestrator HTTP API (POST /plan)"

  # CORS — browser frontend (Next.js, L102/L105) se call ho sake. Prod me origins tight karo.
  cors_configuration {
    allow_origins = var.cors_allow_origins # dev me ["*"], prod me exact domain
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
    max_age       = 300
  }

  tags = { Project = var.project, ManagedBy = "terraform" }
}

# Integration — API GW ko Lambda se jodo (AWS_PROXY = pura request as-is Lambda ko).
# payload_format_version 2.0 = HTTP API ka modern event shape (lab handler isi ko parse karta).
resource "aws_apigatewayv2_integration" "planner_integration" {
  api_id                 = aws_apigatewayv2_api.alex_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.planner.invoke_arn
  payload_format_version = "2.0"
}

# Route — "POST /plan" aaye to upar wale integration par bhej do.
# (Route key me method + path dono — yahi POST /plan ko planner se baandhta hai.)
resource "aws_apigatewayv2_route" "plan_route" {
  api_id    = aws_apigatewayv2_api.alex_api.id
  route_key = "POST /plan"
  target    = "integrations/${aws_apigatewayv2_integration.planner_integration.id}"
}

# Stage — actual deployable endpoint. auto_deploy=true => route change turant live.
# "$default" stage => base URL me extra stage-name nahi (clean URL). access_logs CloudWatch me.
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.alex_api.id
  name        = "$default"
  auto_deploy = true

  # Per-stage throttling (L105: enterprise ke liye super important — abuse/cost-spike brake).
  default_route_settings {
    throttling_burst_limit = var.throttle_burst # ek spike me max concurrent
    throttling_rate_limit  = var.throttle_rate  # steady-state req/sec
  }

  tags = { Project = var.project, ManagedBy = "terraform" }
}

# Permission — API GW ko is Lambda ko invoke karne ki ijaazat do.
# WHY zaroori: IAM role Lambda ka apna hai; yeh ALAG resource-based permission API GW ko
# bolta hai "tum mujhe call kar sakte ho". Bina iske API GW -> 500/403 (AccessDenied).
resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.planner.function_name
  principal     = "apigateway.amazonaws.com"
  # source_arn ko is API ke kisi bhi stage/route tak baandho (least-privilege wildcard).
  source_arn = "${aws_apigatewayv2_api.alex_api.execution_arn}/*/*"
}
