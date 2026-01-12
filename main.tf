terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# ============================================
# S3 Buckets
# ============================================

# Model Registry - Stores versioned model.json files
resource "aws_s3_bucket" "model_registry" {
  bucket = "sherlock-model-registry-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "model_registry" {
  bucket = aws_s3_bucket.model_registry.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Audit Lake - Immutable transaction logs
resource "aws_s3_bucket" "audit_lake" {
  bucket = "sherlock-audit-lake-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "audit_lake" {
  bucket = aws_s3_bucket.audit_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ============================================
# Kinesis Firehose
# ============================================

resource "aws_kinesis_firehose_delivery_stream" "audit_stream" {
  name        = "sherlock-audit-stream"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose_role.arn
    bucket_arn          = aws_s3_bucket.audit_lake.arn
    prefix              = "transactions/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    error_output_prefix = "errors/!{firehose:error-output-type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"

    buffering_size     = 1
    buffering_interval = 60

    compression_format = "GZIP"
  }
}

resource "aws_iam_role" "firehose_role" {
  name = "sherlock-firehose-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "firehose.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "firehose_s3" {
  name = "firehose-s3-policy"
  role = aws_iam_role.firehose_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ]
      Resource = [
        aws_s3_bucket.audit_lake.arn,
        "${aws_s3_bucket.audit_lake.arn}/*"
      ]
    }]
  })
}

# ============================================
# DynamoDB Table
# ============================================

resource "aws_dynamodb_table" "sherlock_state" {
  name         = "sherlock_state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl_window"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name        = "Sherlock State Table"
    Environment = "Production"
  }
}


resource "aws_dynamodb_table" "sherlock_device_graph" {
  name         = "sherlock_device_graph"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "device_id"
  range_key    = "user_id"

  attribute {
    name = "device_id"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "Sherlock Device Graph"
    Environment = "Production"
  }
}

# ============================================
# SQS Queue (Shadow Mode)
# ============================================

resource "aws_sqs_queue" "shadow_dlq" {
  name                      = "sherlock-shadow-dlq"
  message_retention_seconds = 1209600 # 14 days
}

resource "aws_sqs_queue" "shadow_queue" {
  name                       = "sherlock-shadow-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 86400 # 1 day

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.shadow_dlq.arn
    maxReceiveCount     = 3
  })
}

# ============================================
# Lambda Functions
# ============================================

# Champion Lambda
resource "aws_lambda_function" "champion" {
  s3_bucket        = aws_s3_bucket.model_registry.bucket
  s3_key           = "lambda/champion_function.zip"
  function_name    = "sherlock-champion"
  role             = aws_iam_role.champion_role.arn
  handler          = "champion_function.lambda_handler"
  source_code_hash = filebase64sha256("champion_function.zip")
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 2048
  publish          = true

  ephemeral_storage {
    size = 512 # MB - for XGBoost dependencies
  }

  environment {
    variables = {
      DYNAMODB_TABLE   = aws_dynamodb_table.sherlock_state.name
      GRAPH_TABLE      = aws_dynamodb_table.sherlock_device_graph.name
      SHADOW_QUEUE_URL = aws_sqs_queue.shadow_queue.url
      FIREHOSE_STREAM  = aws_kinesis_firehose_delivery_stream.audit_stream.name
      MODEL_BUCKET     = aws_s3_bucket.model_registry.bucket
      MODEL_KEY        = "model.json"
      XGBOOST_DEPS_KEY = "lambda/xgboost_deps.zip"
      SECRET_ARN       = aws_secretsmanager_secret.api_key.arn
    }
  }

  tracing_config {
    mode = "Active"
  }

  # XGBoost dependencies downloaded from S3 to /tmp at runtime
}

resource "aws_lambda_alias" "champion_prod" {
  name             = "prod"
  description      = "Production alias"
  function_name    = aws_lambda_function.champion.function_name
  function_version = aws_lambda_function.champion.version
}

# Shadow Lambda
resource "aws_lambda_function" "shadow" {
  s3_bucket        = aws_s3_bucket.model_registry.bucket
  s3_key           = "lambda/shadow_function.zip"
  function_name    = "sherlock-shadow"
  role             = aws_iam_role.shadow_role.arn
  handler          = "shadow_function.lambda_handler"
  source_code_hash = filebase64sha256("shadow_function.zip")
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      LOG_LEVEL = "INFO"
    }
  }

  tracing_config {
    mode = "Active"
  }
}

# Lambda Layer for XGBoost - Using S3 due to size limit
# Note: Lambda layers have a 70MB limit for direct upload
# For now, we'll bundle dependencies directly with the Champion function
# Alternative: Upload layer to S3 and reference it
# resource "aws_lambda_layer_version" "xgboost_layer" {
#   s3_bucket           = aws_s3_bucket.model_registry.bucket
#   s3_key              = "layers/xgboost-layer.zip"
#   layer_name          = "xgboost-layer"
#   compatible_runtimes = ["python3.11"]
# }

# # Archive Champion Function
# data "archive_file" "champion" {
#   type        = "zip"
#   source_file = "champion_function.py"
#   output_path = "champion_function.zip"
# }

# # Archive Shadow Function
# data "archive_file" "shadow" {
#   type        = "zip"
#   source_file = "shadow_function.py"
#   output_path = "shadow_function.zip"
# }

# SQS Event Source Mapping for Shadow Lambda
resource "aws_lambda_event_source_mapping" "shadow_sqs" {
  event_source_arn = aws_sqs_queue.shadow_queue.arn
  function_name    = aws_lambda_function.shadow.arn
  batch_size       = 10
}

# ============================================
# IAM Roles for Lambda
# ============================================

# Champion Lambda Role
resource "aws_iam_role" "champion_role" {
  name = "sherlock-champion-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "champion_policy" {
  name = "champion-policy"
  role = aws_iam_role.champion_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.sherlock_state.arn,
          aws_dynamodb_table.sherlock_device_graph.arn
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.api_key.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.shadow_queue.arn
      },
      {
        Effect = "Allow"
        Action = [
          "firehose:PutRecord",
          "firehose:PutRecordBatch"
        ]
        Resource = aws_kinesis_firehose_delivery_stream.audit_stream.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.model_registry.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

# Shadow Lambda Role
resource "aws_iam_role" "shadow_role" {
  name = "sherlock-shadow-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "shadow_policy" {
  name = "shadow-policy"
  role = aws_iam_role.shadow_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.shadow_queue.arn
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

# ============================================
# API Gateway
# ============================================

resource "aws_apigatewayv2_api" "sherlock_api" {
  name          = "sherlock-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "GET", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
  }
}

resource "aws_apigatewayv2_integration" "champion_integration" {
  api_id                 = aws_apigatewayv2_api.sherlock_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_alias.champion_prod.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "transaction_route" {
  api_id    = aws_apigatewayv2_api.sherlock_api.id
  route_key = "POST /transaction"
  target    = "integrations/${aws_apigatewayv2_integration.champion_integration.id}"
  # Security Upgrade: Attach Authorizer
  # authorization_type = "CUSTOM"
  # authorizer_id      = aws_apigatewayv2_authorizer.sherlock_auth.id
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.sherlock_api.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    detailed_metrics_enabled = true
    throttling_burst_limit   = 500
    throttling_rate_limit    = 1000
  }
}

# The aws_apigatewayv2_stage resource doesn't directly expose tracing_enabled in some versions/providers
# but we can enable it via the access_log_settings or it's often enabled at the API level if available.
# Actually, for HTTP APIs, it's often enabled via the stage's default_route_settings or similar.
# In AWS API Gateway v2, X-Ray is enabled at the API level or stage level depending on the API type.
# For HTTP APIs, it's usually on the stage.

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvokeProd"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.champion.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.sherlock_api.execution_arn}/*/*"
  qualifier     = aws_lambda_alias.champion_prod.name
}

# ============================================
# SECURITY PACK (WAF, Auth, Secrets)
# ============================================

# 1. Secrets Manager
resource "aws_secretsmanager_secret" "api_key" {
  name        = "sherlock-api-key"
  description = "API Key for Sherlock Fraud Detection"
}

resource "aws_secretsmanager_secret_version" "api_key_val" {
  secret_id     = aws_secretsmanager_secret.api_key.id
  secret_string = "sherlock_secure_2026_prod" # In real life, generate random
}

# 2. Authorizer Lambda (DEPRECATED - Moved to App Layer)
# data "archive_file" "authorizer_zip" {
#   type        = "zip"
#   output_path = "authorizer_function.zip"
#   source_file = "authorizer_function.py"
# }

# resource "aws_lambda_function" "authorizer" {
#   filename         = "authorizer_function.zip"
#   function_name    = "sherlock-authorizer"
#   role             = aws_iam_role.authorizer_role.arn
#   handler          = "authorizer_function.lambda_handler"
#   source_code_hash = data.archive_file.authorizer_zip.output_base64sha256
#   runtime          = "python3.11"

#   environment {
#     variables = {
#       SECRET_ARN = aws_secretsmanager_secret.api_key.arn
#     }
#   }
# }

# resource "aws_apigatewayv2_authorizer" "sherlock_auth" {
#   api_id           = aws_apigatewayv2_api.sherlock_api.id
#   authorizer_type  = "REQUEST"
#   authorizer_uri   = aws_lambda_function.authorizer.invoke_arn
#   identity_sources = ["$request.header.Authorization"]
#   name             = "sherlock-authorizer"
#   authorizer_payload_format_version = "2.0"
#   enable_simple_responses = true
# }

# resource "aws_lambda_permission" "auth_invoke" {
#   statement_id  = "AllowAPIGatewayInvokeAuth"
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.authorizer.function_name
#   principal     = "apigateway.amazonaws.com"
#   source_arn    = "${aws_apigatewayv2_api.sherlock_api.execution_arn}/*"
# }

# 3. IAM for Authorizer (DEPRECATED)
# resource "aws_iam_role" "authorizer_role" {
#   name = "sherlock-authorizer-role"

#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [{
#       Action = "sts:AssumeRole"
#       Effect = "Allow"
#       Principal = { Service = "lambda.amazonaws.com" }
#     }]
#   })
# }

# resource "aws_iam_role_policy" "authorizer_policy" {
#   name = "authorizer-policy"
#   role = aws_iam_role.authorizer_role.id

#   policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Effect = "Allow"
#         Action = ["secretsmanager:GetSecretValue"]
#         Resource = aws_secretsmanager_secret.api_key.arn
#       },
#       {
#         Effect = "Allow"
#         Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
#         Resource = "arn:aws:logs:*:*:*"
#       }
#     ]
#   })
# }

# ============================================
# Data Sources
# ============================================

data "aws_caller_identity" "current" {}
