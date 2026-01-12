"""
Sherlock Champion Lambda Function - Production Hardened
Features: Pydantic validation, Idempotency checks, X-Ray tracing
"""

import json
import os
import sys
import time
import boto3
import zipfile
from typing import Optional
from pydantic import BaseModel, Field, validator
from botocore.exceptions import ClientError

# X-Ray Instrumentation
from aws_xray_sdk.core import xray_recorder, patch_all
patch_all()  # Instrument boto3, requests, etc.

# ============================================
# PYDANTIC MODELS
# ============================================

class TransactionPayload(BaseModel):
    """Validated transaction request payload"""
    transaction_id: str = Field(..., min_length=1, description="Unique transaction identifier")
    user_id: str = Field(..., min_length=1, description="User identifier")
    amount: float = Field(..., gt=0, description="Transaction amount (must be > 0)")
    merchant: str = Field(..., min_length=1, description="Merchant name")
    location: Optional[str] = Field(default="unknown", description="Transaction location")
    device_id: Optional[str] = Field(default=None, description="Device identifier")
    
    @validator('amount')
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        return v


# ============================================
# GLOBAL STATE (Cold Start Optimization)
# ============================================

# Initialize Boto3 clients once per container
dynamodb = boto3.client('dynamodb', region_name='us-east-1')
sqs = boto3.client('sqs', region_name='us-east-1')
firehose = boto3.client('firehose', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')

# Environment variables
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
GRAPH_TABLE = os.environ.get('GRAPH_TABLE')
SHADOW_QUEUE_URL = os.environ['SHADOW_QUEUE_URL']
MODEL_BUCKET = os.environ['MODEL_BUCKET']
MODEL_KEY = os.environ['MODEL_KEY']
XGBOOST_DEPS_KEY = os.environ.get('XGBOOST_DEPS_KEY', 'lambda/xgboost_deps.zip')
SECRET_ARN = os.environ.get('SECRET_ARN')

# Global model variable
xgboost_model = None
MODEL_LOADED = False
DEPS_LOADED = False
SECRET_CACHE = None



def load_dependencies():
    """Download and extract XGBoost dependencies from S3 to /tmp"""
    global DEPS_LOADED
    
    if DEPS_LOADED:
        return
    
    try:
        with xray_recorder.capture('load_dependencies'):
            deps_path = '/tmp/xgboost_deps.zip'
            extract_path = '/tmp/python'
            
            # Check if already extracted
            if os.path.exists(extract_path) and os.path.exists(os.path.join(extract_path, 'xgboost')):
                if extract_path not in sys.path:
                    sys.path.insert(0, extract_path)
                DEPS_LOADED = True
                print("✅ Dependencies already loaded from /tmp")
                return
            
            # Download dependencies from S3
            print(f"Downloading dependencies from s3://{MODEL_BUCKET}/{XGBOOST_DEPS_KEY}")
            s3.download_file(MODEL_BUCKET, XGBOOST_DEPS_KEY, deps_path)
            
            # Extract to /tmp
            print("Extracting dependencies to /tmp/python")
            with zipfile.ZipFile(deps_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            
            # Add to Python path
            sys.path.insert(0, extract_path)
            
            # Cleanup zip file
            os.remove(deps_path)
            
            DEPS_LOADED = True
            print("✅ Dependencies loaded successfully")
        
    except Exception as e:
        print(f"⚠️ Dependency loading failed: {e}")
        DEPS_LOADED = False


def load_model():
    """Load XGBoost model from S3 to /tmp (once per container)"""
    global xgboost_model, MODEL_LOADED
    
    if MODEL_LOADED:
        return
    
    try:
        with xray_recorder.capture('load_model'):
            # First, ensure dependencies are loaded
            load_dependencies()
            
            # Now import xgboost
            import xgboost as xgb
            
            # Download model to /tmp
            local_path = '/tmp/model.json'
            if not os.path.exists(local_path):
                print(f"Downloading model from s3://{MODEL_BUCKET}/{MODEL_KEY}")
                s3.download_file(MODEL_BUCKET, MODEL_KEY, local_path)
            
            # Load XGBoost model
            xgboost_model = xgb.Booster()
            xgboost_model.load_model(local_path)
            MODEL_LOADED = True
            print("✅ Model loaded successfully")
        
    except Exception as e:
        print(f"⚠️ Model loading failed: {e}")
        import traceback
        traceback.print_exc()
        MODEL_LOADED = False
def get_secret():
    """Retrieve API Key from Secrets Manager with caching"""
    global SECRET_CACHE
    
    if not SECRET_ARN:
        print("⚠️ SECRET_ARN not configured, skipping auth")
        return None
        
    if SECRET_CACHE:
        return SECRET_CACHE
    
    try:
        with xray_recorder.capture('get_secret'):
            client = boto3.client('secretsmanager', region_name='us-east-1')
            response = client.get_secret_value(SecretId=SECRET_ARN)
            if 'SecretString' in response:
                SECRET_CACHE = response['SecretString']
                return SECRET_CACHE
    except Exception as e:
        print(f"⚠️ Failed to fetch secret: {e}")
        return None



def check_fraud_ring(device_id, current_user):
    """
    Graph Analysis: Check how many UNIQUE users are linked to this device.
    Returns: (is_fraud_ring, user_count)
    """
    if not device_id or not GRAPH_TABLE:
        return False, 0
    
    try:
        with xray_recorder.capture('graph_analysis_read'):
            response = dynamodb.query(
                TableName=GRAPH_TABLE,
                KeyConditionExpression='device_id = :did',
                ExpressionAttributeValues={':did': {'S': device_id}},
                Select='COUNT',
                ConsistentRead=True
            )
            count = response['Count']
            
            # Simple heuristic: If > 3 users share a device, it's a ring
            if count > 3:
                print(f"🚨 FRAUD RING DETECTED: Device {device_id} used by {count} users")
                return True, count
            return False, count
            
    except Exception as e:
        print(f"⚠️ Graph analysis failed: {e}")
        return False, 0

def record_device_usage(device_id, user_id, current_time):
    """
    Graph Update: Add edge (Device -> User)
    """
    if not device_id or not GRAPH_TABLE:
        return
        
    try:
        with xray_recorder.capture('graph_analysis_write'):
            dynamodb.put_item(
                TableName=GRAPH_TABLE,
                Item={
                    'device_id': {'S': device_id},
                    'user_id': {'S': user_id},
                    'timestamp': {'N': str(current_time)},
                    'ttl': {'N': str(current_time + (86400 * 30))} # Keep history for 30 days
                }
            )
    except Exception as e:
        print(f"⚠️ Graph update failed: {e}")

# ============================================
# HANDLER
# ============================================

@xray_recorder.capture('lambda_handler')
def lambda_handler(event, context):
    """Main handler for fraud detection with production hardening"""
    start_time = time.time()
    
    # Load model on first invocation
    if not MODEL_LOADED:
        load_model()
    
    # ============================================
    # AUTHENTICATION (App Layer)
    # ============================================
    with xray_recorder.capture('authentication'):
        api_key = get_secret()
        if api_key:
            headers = event.get('headers', {})
            # Handle case-insensitive headers (HTTP API v2 lowercases them)
            auth_header = headers.get('authorization', headers.get('Authorization', ''))
            
            if not auth_header or not auth_header.lower().startswith('bearer ') or auth_header.split(' ')[1] != api_key:
                print("⛔ Authentication Failed")
                return {
                    'statusCode': 401,
                    'body': json.dumps({'status': 'UNAUTHORIZED', 'message': 'Invalid API Key'})
                }

    
    try:
        # ============================================
        # INPUT VALIDATION (Pydantic)
        # ============================================
        
        with xray_recorder.capture('input_validation'):
            try:
                body = json.loads(event.get('body', '{}'))
                payload = TransactionPayload(**body)
            except Exception as e:
                latency_ms = round((time.time() - start_time) * 1000, 2)
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'status': 'ERROR',
                        'message': f'Invalid input: {str(e)}',
                        'latency_ms': latency_ms
                    })
                }
        
        # ============================================
        # IDEMPOTENCY CHECK
        # ============================================
        
        current_time = int(time.time())
        ttl_window = current_time + 60  # Expire after 60 seconds
        
        try:
            with xray_recorder.capture('velocity_and_idempotency_check'):
                # Atomic DynamoDB operation with idempotency check
                velocity_response = dynamodb.update_item(
                    TableName=DYNAMODB_TABLE,
                    Key={'user_id': {'S': payload.user_id}},
                    # CRITICAL: Only update if this is a NEW transaction ID
                    ConditionExpression='attribute_not_exists(last_transaction_id) OR last_transaction_id <> :new_tx_id',
                    UpdateExpression='ADD velocity_counter :inc SET last_location = :loc, ttl_window = :ttl, last_transaction_id = :new_tx_id, last_decision = :placeholder_decision',
                    ExpressionAttributeValues={
                        ':inc': {'N': '1'},
                        ':loc': {'S': payload.location},
                        ':ttl': {'N': str(ttl_window)},
                        ':new_tx_id': {'S': payload.transaction_id},
                        ':placeholder_decision': {'S': 'PROCESSING'}  # Will be updated later
                    },
                    ReturnValues='ALL_NEW'
                )
                
                # Extract velocity data
                attributes = velocity_response.get('Attributes', {})
                velocity_counter = int(attributes.get('velocity_counter', {}).get('N', '1'))
                last_location = attributes.get('last_location', {}).get('S', payload.location)
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # IDEMPOTENCY HIT: We already processed this transaction_id
                with xray_recorder.capture('idempotent_replay'):
                    print(f"⚠️ IDEMPOTENT REPLAY detected for transaction_id: {payload.transaction_id}")
                    
                    # Fetch the existing record
                    existing_record = dynamodb.get_item(
                        TableName=DYNAMODB_TABLE,
                        Key={'user_id': {'S': payload.user_id}}
                    )
                    
                    last_decision = existing_record.get('Item', {}).get('last_decision', {}).get('S', 'UNKNOWN')
                    last_risk_score = float(existing_record.get('Item', {}).get('last_risk_score', {}).get('N', 0))
                    
                    latency_ms = round((time.time() - start_time) * 1000, 2)
                    
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({
                            'status': last_decision,
                            'transaction_id': payload.transaction_id,
                            'risk_score': last_risk_score,
                            'reasons': ['IDEMPOTENT_REPLAY'],
                            'velocity_counter': 0,  # Not incremented
                            'latency_ms': latency_ms,
                            'idempotent': True
                        })
                    }
            else:
                raise  # Re-raise other errors
        
        # Fraud flags
        high_velocity = velocity_counter > 5
        impossible_travel = (last_location != payload.location and velocity_counter > 1)
        
        # Graph Analysis (Fraud Ring)
        is_fraud_ring = False
        linked_users = 0
        
        if payload.device_id:
            # 1. Update the graph (Async pattern simulated by non-blocking call)
            record_device_usage(payload.device_id, payload.user_id, current_time)
            
            # 2. Check for rings
            is_fraud_ring, linked_users = check_fraud_ring(payload.device_id, payload.user_id)

        
        # ============================================
        # AI INFERENCE
        # ============================================
        
        risk_score = 0
        with xray_recorder.capture('ai_inference'):
            if MODEL_LOADED and xgboost_model:
                try:
                    import xgboost as xgb
                    import numpy as np
                    
                    # Feature engineering
                    features = np.array([[
                        payload.amount,
                        velocity_counter,
                        1 if impossible_travel else 0,
                        hash(payload.merchant) % 1000,
                        hash(payload.location) % 100
                    ]], dtype=np.float32)
                    
                    dmatrix = xgb.DMatrix(features)
                    prediction = xgboost_model.predict(dmatrix)
                    risk_score = float(prediction[0]) * 100
                    
                except Exception as e:
                    print(f"⚠️ Inference error: {e}")
                    risk_score = 50 + (velocity_counter * 5) + (20 if impossible_travel else 0)
            else:
                risk_score = 50 + (velocity_counter * 5) + (20 if impossible_travel else 0)
        
        # ============================================
        # DECISION LOGIC
        # ============================================
        
        reasons = []
        if high_velocity:
            reasons.append("HIGH_VELOCITY")
        if impossible_travel:
            reasons.append("IMPOSSIBLE_TRAVEL")
        if risk_score > 80:
            reasons.append("HIGH_RISK_SCORE")
        if is_fraud_ring:
            reasons.append(f"FRAUD_RING_DETECTED_USERS_{linked_users}")

        
        decision = "BLOCK" if reasons else "ALLOW"
        
        # ============================================
        # UPDATE DECISION IN DYNAMODB
        # ============================================
        
        with xray_recorder.capture('update_decision'):
            dynamodb.update_item(
                TableName=DYNAMODB_TABLE,
                Key={'user_id': {'S': payload.user_id}},
                UpdateExpression='SET last_decision = :decision, last_risk_score = :risk_score',
                ExpressionAttributeValues={
                    ':decision': {'S': decision},
                    ':risk_score': {'N': str(round(risk_score, 2))}
                }
            )
        
        # ============================================
        # AUDIT TRAIL (Non-blocking)
        # ============================================
        
        with xray_recorder.capture('audit_logging'):
            audit_record = {
                'transaction_id': payload.transaction_id,
                'user_id': payload.user_id,
                'amount': payload.amount,
                'location': payload.location,
                'merchant': payload.merchant,
                'device_id': payload.device_id,
                'velocity_counter': velocity_counter,
                'last_location': last_location,
                'risk_score': round(risk_score, 2),
                'decision': decision,
                'reasons': reasons,
                'timestamp': current_time
            }
            
            try:
                firehose.put_record(
                    DeliveryStreamName=FIREHOSE_STREAM,
                    Record={'Data': json.dumps(audit_record) + '\n'}
                )
            except Exception as e:
                print(f"⚠️ Audit logging failed: {e}")
        
        # ============================================
        # SHADOW MODE DISPATCH
        # ============================================
        
        with xray_recorder.capture('shadow_dispatch'):
            shadow_payload = {
                'transaction': body,
                'champion_decision': decision,
                'champion_risk_score': round(risk_score, 2),
                'timestamp': current_time
            }
            
            try:
                sqs.send_message(
                    QueueUrl=SHADOW_QUEUE_URL,
                    MessageBody=json.dumps(shadow_payload)
                )
            except Exception as e:
                print(f"⚠️ Shadow dispatch failed: {e}")
        
        # ============================================
        # RESPONSE
        # ============================================
        
        latency_ms = round((time.time() - start_time) * 1000, 2)
        
        response_body = {
            'status': decision,
            'transaction_id': payload.transaction_id,
            'risk_score': round(risk_score, 2),
            'reasons': reasons,
            'velocity_counter': velocity_counter,
            'latency_ms': latency_ms,
            'model_loaded': MODEL_LOADED,
            'idempotent': False
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'ERROR',
                'message': str(e)
            })
        }
