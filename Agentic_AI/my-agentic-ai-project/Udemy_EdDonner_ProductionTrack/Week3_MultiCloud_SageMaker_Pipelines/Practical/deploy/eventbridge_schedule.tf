# =============================================================================
# eventbridge_schedule.tf  --  EventBridge SCHEDULE -> Lambda (managed cron wiring)
# =============================================================================
# KYA HAI YEH FILE (Hinglish):
#   Lab 6 (lab6_eventbridge_scheduled_agent.py) ka deploy side. Yeh wahi "Alex
#   Scheduler" automation hai (L87): ek SCHEDULE har N ghante/minute par ek Lambda
#   ko fire karta hai jo research/ingest run kick karta. ClickOps me yeh AWS console
#   me rule banao -> target jodo -> permission do -- yahan sab DECLARATIVE HCL me.
#
#   3 RESOURCES milke kaam karte hain (yaad rakhne wala triple):
#     1) aws_cloudwatch_event_rule    -> KAB fire karna (schedule_expression)
#     2) aws_cloudwatch_event_target  -> KYA invoke karna (rule -> Lambda)
#     3) aws_lambda_permission        -> EventBridge ko Lambda INVOKE karne ki
#                                        IJAAZAT (warna rule fire hoga par invoke
#                                        AccessDenied -- #1 silent gotcha)
#
#   PUSH vs PULL: classic cron = PULL (always-on box har minute check). EventBridge
#   = PUSH (AWS managed scheduler time aane par tumhare Lambda ko push karta) --
#   koi server nahi, idle = $0. (L87 ka "managed cron, no crontab box" sabak.)
#
#   COST DISCIPLINE (L87/L88): yeh schedule cost-bearing hai (har tick ek research
#   run = Bedrock+SageMaker+S3). Isliye `scheduler_enabled` flag + CONDITIONAL
#   resource (`count = var.scheduler_enabled ? 1 : 0`) -- flag false => 0 resource
#   bante (automation OFF), bina code delete kiye. Yahi Ed ka one-line on/off.
#
#   NOTE (do scheduling APIs): Ed ne lecture me NAYA `aws_scheduler_schedule`
#   (EventBridge Scheduler service -- timezone support, one-time schedules)
#   use kiya. Yeh file CLASSIC `aws_cloudwatch_event_rule` triple dikhati hai
#   kyunki wahi Lambda-invoke wiring (rule+target+permission) ko sabse saaf
#   expose karti hai. DONO real AWS scheduling hain; rule = UTC-only + recurring,
#   scheduler = newer + timezone-aware. Choose per need.
# =============================================================================


# -----------------------------------------------------------------------------
# VARIABLES -- is file ke knobs (asli stack me variables.tf me hote; yahan inline
# rakhe taaki yeh file self-contained padhi jaa sake).
# -----------------------------------------------------------------------------

# scheduler_enabled: ek-line feature flag (L87). true => schedule banega aur
# automation ON; false => 0 resources (automation OFF), code waise ka waisa.
variable "scheduler_enabled" {
  description = "true => EventBridge schedule create karo (automation ON, cost-bearing). false => kuch nahi."
  type        = bool
  default     = false # SAFE default: galti se cost on na ho jaaye (L88 cost discipline)
}

# schedule_expression: KAB chalana. rate(...) = fixed interval; cron(...) = exact
# wall-clock (UTC). Ed ne L87 me rate(2 hours) rakha. Demo ke liye rate(10 minutes)
# bhi chalta. (Python lab ka explain_schedule() inhi expressions ko validate karta.)
variable "schedule_expression" {
  description = "EventBridge schedule, e.g. rate(2 hours) ya cron(0 9 * * ? *) (UTC)."
  type        = string
  default     = "rate(2 hours)"
}

# research_lambda_arn / name: jis Lambda ko schedule invoke karega (Alex Scheduler
# = lab6 ka handler, deployed). Asli stack me yeh aws_lambda_function.scheduler.arn
# ko reference karta; yahan variable se inject karte hain taaki file standalone rahe.
variable "research_lambda_arn" {
  description = "Schedule jis Lambda ko invoke karega uska ARN (Alex Scheduler / lab6 handler)."
  type        = string
  default     = "arn:aws:lambda:us-east-1:123456789012:function:alex-scheduler"
}

variable "research_lambda_name" {
  description = "Wahi Lambda ka function name (lambda_permission ke liye chahiye)."
  type        = string
  default     = "alex-scheduler"
}

variable "name_prefix" {
  description = "Resource naming prefix (env separation: alex-dev / alex-prod)."
  type        = string
  default     = "alex"
}


# -----------------------------------------------------------------------------
# 1) EVENT RULE -- KAB fire karna. (managed cron ka dil)
# -----------------------------------------------------------------------------
# count = var.scheduler_enabled ? 1 : 0  -- Terraform ka CONDITIONAL RESOURCE
# pattern (L87). flag true => 1 resource (list of length 1), false => 0 (kuch
# nahi banta). Isi liye neeche references me [0] index lagta hai.
#
# schedule_expression: yahi wo rate()/cron() hai jo upar variable se aata. is_enabled
# = true taaki rule bante hi active ho. (is_enabled=false rakh ke pause bhi kar sakte.)
resource "aws_cloudwatch_event_rule" "research_schedule" {
  count = var.scheduler_enabled ? 1 : 0 # flag se create-or-not (cost on/off)

  name                = "${var.name_prefix}-research-schedule"
  description         = "Har tick par research/ingest run kick karta (L87 Alex Scheduler)."
  schedule_expression = var.schedule_expression # rate(2 hours) ya cron(...) UTC
  state               = "ENABLED"               # bante hi active. PAUSE chahiye to "DISABLED"
}

# -----------------------------------------------------------------------------
# 2) EVENT TARGET -- KYA invoke karna. (rule -> Lambda)
# -----------------------------------------------------------------------------
# target = "is rule ke fire hone par yeh resource chalao". Yahan arn = research
# Lambda ka ARN. target_id rule ke andar ek logical handle hai (ek rule ke multiple
# targets ho sakte; har ek ka unique id).
#
# input: scheduled event ka detail by default khaali ({}) hota. Hum ek custom
# constant payload bhej sakte hain (job ko hint dene ko). Yahan ek chhota JSON
# bhejte hain -- par dhyan: handler abhi bhi source/detail-type check karta hai
# (jo EventBridge khud bharta), isliye yeh custom input upar-se merge hota hai.
resource "aws_cloudwatch_event_target" "research_lambda" {
  count = var.scheduler_enabled ? 1 : 0 # rule ke saath hi banega/mitega

  rule      = aws_cloudwatch_event_rule.research_schedule[0].name # kis rule ka target
  target_id = "${var.name_prefix}-research-lambda"
  arn       = var.research_lambda_arn # <-- yahi Lambda invoke hoga (Alex Scheduler)

  # input = optional constant payload (JSON string). EventBridge isse event me
  # daal deta. Job-specific hint dene ka tareeka (e.g. konsi pipeline kick karni).
  input = jsonencode({
    job    = "research_auto"
    source = "eventbridge-schedule"
  })
}

# -----------------------------------------------------------------------------
# 3) LAMBDA PERMISSION -- EventBridge ko Lambda INVOKE karne ki ijaazat.
# -----------------------------------------------------------------------------
# YEH SABSE BHOOLA-JAANE-WALA STEP HAI (#1 gotcha): rule + target laga diya par
# bina is permission ke EventBridge Lambda ko invoke nahi kar paata -- rule "fire"
# hota dikhta par kuch nahi chalta (silent). Yeh resource-based policy Lambda par
# lagti hai: "events.amazonaws.com (EventBridge) ko ijaazat hai is function ko
# invoke karne ki".
#
# source_arn = rule ka ARN -- LEAST PRIVILEGE: sirf YAHI rule invoke kar sake, koi
# random caller nahi. (Bina source_arn ke koi bhi EventBridge rule tumhara Lambda
# trigger kar sakta = security hole.)
resource "aws_lambda_permission" "allow_eventbridge" {
  count = var.scheduler_enabled ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = var.research_lambda_name        # kis Lambda par permission
  principal     = "events.amazonaws.com"          # EventBridge service
  source_arn    = aws_cloudwatch_event_rule.research_schedule[0].arn # sirf is rule se
}


# -----------------------------------------------------------------------------
# OUTPUTS -- apply ke baad confirm: schedule laga ya nahi, kya expression.
# -----------------------------------------------------------------------------
# try(...) isliye: jab scheduler_enabled=false (count=0), resource list khaali
# hoti hai aur [0] index error deta. try() us case me fallback value de deta --
# yaani "disabled" clean dikhe, plan crash na ho.
output "schedule_status" {
  description = "Automation ON hai ya OFF (scheduler_enabled flag ka asar)."
  value       = var.scheduler_enabled ? "ENABLED" : "DISABLED (scheduler_enabled=false)"
}

output "schedule_rule_name" {
  description = "Bana hua rule ka naam (disabled hone par null)."
  value       = try(aws_cloudwatch_event_rule.research_schedule[0].name, null)
}

output "schedule_expression_used" {
  description = "Jo schedule expression apply hua (rate/cron)."
  value       = var.schedule_expression
}
