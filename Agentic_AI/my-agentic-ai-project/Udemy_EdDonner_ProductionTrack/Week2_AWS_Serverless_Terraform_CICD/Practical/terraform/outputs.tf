# =============================================================================
# outputs.tf  --  apply ke baad jo values BAHAR aati hain.
# =============================================================================
# WHY (Hinglish): outputs sirf "vanity print" nahi hain (L53 ka point). Yeh
# ek CONTRACT/INTERFACE hai downstream automation ke liye. Deploy script
# `terraform output -raw api_endpoint` se URL nikaal ke frontend me inject
# karta hai (NEXT_PUBLIC_API_URL). Isliye outputs ko ek API ki tarah treat karo.
#
# Ed L53 me galti se outputs.tf "skip" kar gaya tha, phir wapas aaya -- yeh
# yaad dilata hai ki outputs zaroori hai, optional nahi.
# =============================================================================

output "api_endpoint" {
  description = "API Gateway HTTP endpoint URL -- frontend/curl yahi call karte hain."
  value       = aws_apigatewayv2_api.http.api_endpoint
}

output "memory_bucket_name" {
  description = "Conversation memory S3 bucket ka naam (env-prefixed + account-id suffixed)."
  value       = aws_s3_bucket.memory.bucket
}

output "lambda_function_name" {
  description = "Deploy hui Lambda function ka naam (logs/console me dhoondhne ke liye)."
  value       = aws_lambda_function.api.function_name
}

output "log_group_name" {
  description = "CloudWatch log group jahan Lambda apne logs likhta hai."
  value       = aws_cloudwatch_log_group.lambda.name
}
