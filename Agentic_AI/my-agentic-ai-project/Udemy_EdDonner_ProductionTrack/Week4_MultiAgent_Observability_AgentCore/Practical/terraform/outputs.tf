# =============================================================================
# outputs.tf — apply ke baad jo VALUES chahiye (test/verify/integrate karne ke liye)
# =============================================================================
# WHY outputs: apply ke baad terraform khud ye print karta hai (aur `terraform output`
# se bhi milte). frontend / test_full.py ko API URL chahiye, debugging ko log group chahiye.
# =============================================================================

output "api_endpoint" {
  description = "API Gateway ka base URL. POST <yeh>/plan = planner orchestrator invoke."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "plan_url" {
  description = "Seedha POST karne layak full URL (L106 ka 'test live' yahin hit hota)."
  # invoke_url me trailing slash ho sakta — trimsuffix se double-slash bachao.
  value = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/plan"
}

output "lambda_function_name" {
  description = "Planner Lambda ka naam — `aws lambda invoke` / deploy_all_lambdas.py ke liye."
  value       = aws_lambda_function.planner.function_name
}

output "lambda_function_arn" {
  description = "Planner Lambda ka ARN."
  value       = aws_lambda_function.planner.arn
}

output "log_group_name" {
  description = "CloudWatch log group — `aws logs tail <yeh> --follow` se live logs dekho."
  value       = aws_cloudwatch_log_group.planner_logs.name
}

output "exec_role_arn" {
  description = "Lambda execution role ARN (IAM debugging / audit ke liye)."
  value       = aws_iam_role.planner_exec.arn
}
