#!/bin/bash

# Build Champion Lambda Package (Minimal + Logic Dependencies)
# Includes pydantic and aws-xray-sdk (small)
# Keeps xgboost and numpy in the large S3-based deps zip

set -e

echo "🔨 Building Champion Lambda Package with logic dependencies..."

# Create temporary directory
PACKAGE_DIR="champion_package"
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
echo "📦 Installing Pydantic and X-Ray SDK..."
$PYTHON_CMD -m pip install --target $PACKAGE_DIR \
    pydantic==2.5.2 \
    pydantic-core==2.14.5 \
    aws-xray-sdk==2.12.0 \
    annotated-types==0.6.0 \
    typing-extensions==4.8.0 \
    --no-cache-dir \
    -q

# Copy Lambda function code
echo "📄 Copying Lambda function code..."
cp champion_function.py $PACKAGE_DIR/

# Create zip file
echo "📦 Creating champion_function.zip..."
cd $PACKAGE_DIR
zip -r9 ../champion_function.zip . -q
cd ..

# Cleanup
rm -rf $PACKAGE_DIR

# Get size
SIZE=$(du -h champion_function.zip | cut -f1)
echo "✅ Champion package created: champion_function.zip ($SIZE)"
