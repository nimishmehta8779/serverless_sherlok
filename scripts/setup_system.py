"""
System Setup Utility
Creates dummy XGBoost model and uploads to S3
"""

import json
import boto3
import numpy as np
import xgboost as xgb
from sklearn.datasets import make_classification
import requests
import time


def create_dummy_model():
    """Create a minimal XGBoost model for fraud detection"""
    print("🔨 Creating dummy XGBoost model...")
    
    # Generate synthetic fraud detection data
    # Features: [amount, velocity_counter, impossible_travel, merchant_hash, location_hash]
    X, y = make_classification(
        n_samples=1000,
        n_features=5,
        n_informative=4,
        n_redundant=1,
        n_classes=2,
        weights=[0.9, 0.1],  # 10% fraud rate
        random_state=42
    )
    
    # Train XGBoost model
    dtrain = xgb.DMatrix(X, label=y)
    
    params = {
        'objective': 'binary:logistic',
        'max_depth': 3,
        'eta': 0.1,
        'eval_metric': 'auc'
    }
    
    model = xgb.train(params, dtrain, num_boost_round=10)
    
    # Save model
    model_path = 'model.json'
    model.save_model(model_path)
    
    print(f"✅ Model saved to {model_path}")
    return model_path


def upload_to_s3(bucket_name, model_path='model.json'):
    """Upload model to S3 Model Registry"""
    print(f"📤 Uploading model to s3://{bucket_name}/model.json...")
    
    s3 = boto3.client('s3', region_name='us-east-1')
    
    try:
        s3.upload_file(model_path, bucket_name, 'model.json')
        print(f"✅ Model uploaded successfully")
        
        # Verify upload
        response = s3.head_object(Bucket=bucket_name, Key='model.json')
        print(f"   Size: {response['ContentLength']} bytes")
        print(f"   Version: {response.get('VersionId', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        raise


def test_api(api_url):
    """Send a test transaction to the API"""
    print(f"\n🧪 Testing API: {api_url}")
    
    test_transaction = {
        'user_id': 'test_user_001',
        'amount': 150.00,
        'location': 'New York',
        'merchant': 'Amazon',
        'transaction_id': f'test_txn_{int(time.time())}'
    }
    
    print(f"   Sending: {json.dumps(test_transaction, indent=2)}")
    
    try:
        start_time = time.time()
        response = requests.post(
            api_url,
            json=test_transaction,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        latency = (time.time() - start_time) * 1000
        
        print(f"\n📊 Response:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Latency: {latency:.2f}ms")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Decision: {result.get('status')}")
            print(f"   Risk Score: {result.get('risk_score')}")
            print(f"   Reasons: {result.get('reasons')}")
            print(f"   Server Latency: {result.get('latency_ms')}ms")
            print("✅ API test successful!")
        else:
            print(f"❌ API test failed: {response.text}")
            
    except Exception as e:
        print(f"❌ API test error: {e}")


def main():
    """Main setup workflow"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python setup_system.py <model_bucket_name> [api_url]")
        print("\nExample:")
        print("  python setup_system.py sherlock-model-registry-123456789012")
        print("  python setup_system.py sherlock-model-registry-123456789012 https://abc123.execute-api.us-east-1.amazonaws.com/transaction")
        sys.exit(1)
    
    bucket_name = sys.argv[1]
    api_url = sys.argv[2] if len(sys.argv) > 2 else None
    
    print("=" * 60)
    print("🚀 Sherlock System Setup")
    print("=" * 60)
    
    # Step 1: Create model
    model_path = create_dummy_model()
    
    # Step 2: Upload to S3
    upload_to_s3(bucket_name, model_path)
    
    # Step 3: Test API (if provided)
    if api_url:
        test_api(api_url)
    else:
        print("\n⚠️ No API URL provided, skipping API test")
        print("   Run with API URL to test: python setup_system.py <bucket> <api_url>")
    
    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
