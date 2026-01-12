# Security Policy

## Authentication & Authorization
This project uses **AWS Secrets Manager** to handle API Keys. 
- No hardcoded secrets exist in the source code.
- `SECRET_ARN` is injected into Lambda functions at runtime via Terraform.

## IAM Roles
Least-privilege IAM roles are defined in `main.tf`. 
- `champion_role`: Access to DynamoDB, S3 (Model Registry), and Secrets Manager (GetSecretValue).
- `shadow_role`: Access to SQS and Cloudwatch.

## Reporting Vulnerabilities
If you discover a security issue, please open an issue or contact the maintainer directly.
