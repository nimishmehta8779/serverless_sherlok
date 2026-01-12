#!/bin/bash

# Quick Deployment Script for Serverless Sherlock
# This script automates the entire deployment process

set -e

echo "🚀 Serverless Sherlock - Quick Deployment"
echo "=========================================="
echo ""

# Step 1: Build Lambda Layer
echo "📦 Step 1/4: Building Lambda Layer..."
if [ ! -f "lambda_layer.zip" ]; then
    ./build_lambda_package.sh
else
    echo "✅ Lambda layer already exists (lambda_layer.zip)"
fi
echo ""

# Step 2: Deploy Infrastructure
echo "🏗️  Step 2/4: Deploying Infrastructure..."
terraform init -upgrade
terraform apply -auto-approve

echo ""
echo "✅ Infrastructure deployed!"
echo ""

# Step 3: Get Outputs
echo "📊 Step 3/4: Retrieving Outputs..."
MODEL_BUCKET=$(terraform output -raw model_registry_bucket)
API_URL=$(terraform output -raw api_invoke_url)

echo "   Model Bucket: $MODEL_BUCKET"
echo "   API URL: $API_URL"
echo ""

# Step 4: Setup Model
echo "🤖 Step 4/4: Creating and Uploading Model..."
python3.11 setup_system.py "$MODEL_BUCKET" "$API_URL"

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "📝 Next Steps:"
echo "   1. Run load test: python3.11 load_test.py $API_URL"
echo "   2. Monitor logs: aws logs tail /aws/lambda/sherlock-champion --follow"
echo "   3. Check shadow conflicts: aws logs tail /aws/lambda/sherlock-shadow --follow"
echo ""
echo "🔗 API Endpoint: $API_URL"
echo ""
