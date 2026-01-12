#!/bin/bash

# Build Lambda Layer with XGBoost and dependencies
# This creates a lambda_layer.zip file for use with AWS Lambda

set -e

echo "🔨 Building Lambda Layer for XGBoost..."

# Create temporary directory
LAYER_DIR="python"
rm -rf $LAYER_DIR
mkdir -p $LAYER_DIR

# Check if python3.11 is available
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    echo "✅ Using Python 3.11"
else
    PYTHON_CMD="python3"
    echo "⚠️  Python 3.11 not found, using default python3"
fi

# Install dependencies
echo "📦 Installing dependencies..."
$PYTHON_CMD -m pip install --target $LAYER_DIR \
    --upgrade pip setuptools wheel \
    -q

$PYTHON_CMD -m pip install --target $LAYER_DIR \
    xgboost==1.7.6 \
    numpy==1.24.3 \
    scipy==1.10.1 \
    --no-cache-dir \
    -q

# Create zip file
echo "📦 Creating lambda_layer.zip..."
zip -r lambda_layer.zip $LAYER_DIR -q

# Cleanup
rm -rf $LAYER_DIR

# Get size
SIZE=$(du -h lambda_layer.zip | cut -f1)
echo "✅ Lambda layer created: lambda_layer.zip ($SIZE)"

# Verify contents
echo ""
echo "📋 Layer contents:"
unzip -l lambda_layer.zip | grep -E "(xgboost|numpy)" | head -5
echo "   ..."

echo ""
echo "✅ Build complete!"
echo "   Use this file in Terraform: lambda_layer.zip"
