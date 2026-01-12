#!/bin/bash

# Build Shadow Lambda Package (Minimal + Tracing)
# Includes aws-xray-sdk

set -e

echo "🔨 Building Shadow Lambda Package..."

# Create temporary directory
PACKAGE_DIR="shadow_package"
rm -rf $PACKAGE_DIR
mkdir -p $PACKAGE_DIR

# Check if python3.11 is available
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    echo "✅ Using Python 3.11"
else
    PYTHON_CMD="python3"
    echo "⚠️  Python 3.11 not found, using default python3"
fi

# Install logic dependencies (small)
echo "📦 Installing X-Ray SDK..."
$PYTHON_CMD -m pip install --target $PACKAGE_DIR \
    aws-xray-sdk==2.12.0 \
    --no-cache-dir \
    -q

# Copy Lambda function code
echo "📄 Copying Lambda function code..."
cp shadow_function.py $PACKAGE_DIR/

# Create zip file
echo "📦 Creating shadow_function.zip..."
cd $PACKAGE_DIR
zip -r9 ../shadow_function.zip . -q
cd ..

# Cleanup
rm -rf $PACKAGE_DIR

# Get size
SIZE=$(du -h shadow_function.zip | cut -f1)
echo "✅ Shadow package created: shadow_function.zip ($SIZE)"
