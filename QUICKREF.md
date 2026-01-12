# Serverless Sherlock - Quick Reference

## 🚀 Quick Deploy

```bash
cd /home/rockylinux/devel/serveless_sherlok
chmod +x deploy.sh
./deploy.sh
```

## 📋 Common Commands

### Deploy Infrastructure
```bash
terraform init
terraform apply -auto-approve
```

### Get Outputs
```bash
MODEL_BUCKET=$(terraform output -raw model_registry_bucket)
API_URL=$(terraform output -raw api_invoke_url)
echo "API: $API_URL"
```

### Upload Model
```bash
python3.11 setup_system.py $MODEL_BUCKET $API_URL
```

### Run Load Test
```bash
python3.11 load_test.py $API_URL 100 50
```

### Test Single Transaction
```bash
curl -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "amount": 250.00,
    "location": "New York",
    "merchant": "Amazon"
  }'
```

## 📊 Monitoring

### View Champion Logs
```bash
aws logs tail /aws/lambda/sherlock-champion --follow
```

### View Shadow Logs (Conflicts)
```bash
aws logs tail /aws/lambda/sherlock-shadow --follow
```

### Check DynamoDB State
```bash
aws dynamodb scan --table-name sherlock_state --region us-east-1
```

### List Audit Logs
```bash
AUDIT_BUCKET=$(terraform output -raw audit_lake_bucket)
aws s3 ls s3://$AUDIT_BUCKET/transactions/ --recursive
```

## 🧹 Cleanup

### Destroy All Resources
```bash
terraform destroy -auto-approve
```

### Clean Local Files
```bash
rm -rf .terraform/ *.zip python/ model.json *.tfstate*
```

## 🎯 Fraud Scenarios

### High Velocity Test
```bash
for i in {1..7}; do
  curl -X POST $API_URL -H "Content-Type: application/json" \
    -d '{"user_id": "user_velocity", "amount": 100, "location": "NYC", "merchant": "Store"}'
  sleep 1
done
```

### Impossible Travel Test
```bash
# Transaction 1: New York
curl -X POST $API_URL -d '{"user_id": "user_travel", "location": "New York", "amount": 100, "merchant": "Store"}'

# Transaction 2: Tokyo (seconds later)
curl -X POST $API_URL -d '{"user_id": "user_travel", "location": "Tokyo", "amount": 100, "merchant": "Store"}'
```

## 📈 Performance Targets

- **Latency**: <50ms (server-side)
- **Success Rate**: >99%
- **Throughput**: 50+ req/sec
- **Cost**: ~$7/month for 1M transactions

## 🔧 Troubleshooting

### Lambda Cold Start
- First request may take >500ms
- Subsequent requests should be <50ms
- Use provisioned concurrency for consistent latency

### Model Not Found
```bash
python3.11 setup_system.py $(terraform output -raw model_registry_bucket)
```

### High Latency
- Check CloudWatch Logs for bottlenecks
- Increase Lambda memory (faster CPU)
- Verify DynamoDB is in us-east-1

### Shadow Queue Backlog
```bash
aws lambda put-function-concurrency \
  --function-name sherlock-shadow \
  --reserved-concurrent-executions 100
```

## 📁 Project Structure

```
serveless_sherlok/
├── main.tf                    # Terraform infrastructure
├── outputs.tf                 # Terraform outputs
├── champion_function.py       # Main fraud detection Lambda
├── shadow_function.py         # Shadow model Lambda
├── setup_system.py            # Model setup utility
├── load_test.py               # Load testing script
├── build_lambda_package.sh    # Lambda layer builder
├── deploy.sh                  # Automated deployment
├── requirements.txt           # Python dependencies
├── README.md                  # Full documentation
└── .gitignore                 # Git exclusions
```

## 🔗 Key Resources

- **API Gateway**: POST /transaction
- **DynamoDB**: sherlock_state (TTL enabled)
- **S3**: Model Registry (versioned)
- **S3**: Audit Lake (immutable logs)
- **Kinesis**: Firehose audit stream
- **SQS**: Shadow queue
- **Lambda**: Champion (512MB, 10s timeout)
- **Lambda**: Shadow (256MB, 30s timeout)

## 🎓 Fraud Detection Rules

1. **High Velocity**: velocity_counter > 5 in 60s → BLOCK
2. **Impossible Travel**: Different location + velocity > 1 → BLOCK
3. **High Risk**: XGBoost score > 80 → BLOCK

## 💡 Tips

- Use `deploy.sh` for first-time setup
- Monitor shadow conflicts to validate new models
- Check audit logs in S3 for compliance
- Use load_test.py to benchmark performance
- Enable CloudWatch alarms for production
