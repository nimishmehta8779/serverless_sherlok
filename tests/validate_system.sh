#!/bin/bash

# Sherlock Production Validation Runner
# Wraps the Python validation suite with clean output

set -e

# Configuration
API_URL="https://fkijxo8fxi.execute-api.us-east-1.amazonaws.com/transaction"
PYTHON_CMD="python3.11"

echo "============================================================"
echo "🛡️  SHERLOCK PRODUCTION VALIDATION BOOTSTRAP"
echo "============================================================"
echo "📡 Target: $API_URL"
echo "🕒 Time: $(date)"
echo "============================================================"

# Check if production_validation.py exists
if [ ! -f "production_validation.py" ]; then
    echo "❌ Error: production_validation.py not found in current directory."
    exit 1
fi

# Run the validation suite
echo "🧪 Running Automated Scenarios..."
$PYTHON_CMD production_validation.py

echo "============================================================"
echo "✨ VALIDATION COMPLETE"
echo "============================================================"
echo "💡 Tip: To see real-time distributed traces, visit the AWS X-Ray Console."
echo "💡 Tip: Check DynamoDB 'sherlock_state' for record persistence."
echo "============================================================"
