#!/bin/bash

# Build Lambda Dependencies Package for S3
# This creates a package with XGBoost that will be downloaded at runtime

set -e

echo "🔨 Building XGBoost Dependencies Package for S3..."

# Create temporary directory
DEPS_DIR="xgboost_deps"
rm -rf $DEPS_DIR
mkdir -p $DEPS_DIR

# Check if python3.11 is available
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    echo "✅ Using Python 3.11"
else
    PYTHON_CMD="python3"
    echo "⚠️  Python 3.11 not found, using default python3"
fi

# Install XGBoost and NumPy
echo "📦 Installing XGBoost and NumPy..."
$PYTHON_CMD -m pip install --target $DEPS_DIR \
    xgboost==1.7.6 \
    numpy==1.24.3 \
    --no-cache-dir \
    -q

echo "🧹 Removing unnecessary files..."
cd $DEPS_DIR

# Remove test files and documentation
find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

cd ..

# Create zip file
echo "📦 Creating xgboost_deps.zip..."
cd $DEPS_DIR
zip -r9 ../xgboost_deps.zip . -q
cd ..

# Cleanup
rm -rf $DEPS_DIR

# Get size
SIZE=$(du -h xgboost_deps.zip | cut -f1)
echo "✅ Dependencies package created: xgboost_deps.zip ($SIZE)"

echo ""
echo "✅ Build complete!"
echo "   This will be uploaded to S3 and downloaded to /tmp at runtime"
