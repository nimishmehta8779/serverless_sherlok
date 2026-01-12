output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.sherlock_api.api_endpoint
}

output "api_invoke_url" {
  description = "Full API invoke URL for POST /transaction"
  value       = "${aws_apigatewayv2_api.sherlock_api.api_endpoint}/transaction"
}

output "model_registry_bucket" {
  description = "S3 bucket name for model registry"
  value       = aws_s3_bucket.model_registry.bucket
}

output "audit_lake_bucket" {
  description = "S3 bucket name for audit lake"
  value       = aws_s3_bucket.audit_lake.bucket
}

output "dynamodb_table_name" {
  description = "DynamoDB table name for state management"
  value       = aws_dynamodb_table.sherlock_state.name
}

output "shadow_queue_url" {
  description = "SQS queue URL for shadow mode"
  value       = aws_sqs_queue.shadow_queue.url
}

output "champion_lambda_arn" {
  description = "Champion Lambda function ARN"
  value       = aws_lambda_function.champion.arn
}

output "shadow_lambda_arn" {
  description = "Shadow Lambda function ARN"
  value       = aws_lambda_function.shadow.arn
}

output "firehose_stream_name" {
  description = "Kinesis Firehose stream name"
  value       = aws_kinesis_firehose_delivery_stream.audit_stream.name
}
