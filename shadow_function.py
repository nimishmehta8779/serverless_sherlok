"""
Sherlock Shadow Lambda Function
Simulates heavy Deep Learning model for safe A/B testing
Production hardened with X-Ray tracing
"""

import json
import time
import random

# X-Ray Instrumentation
from aws_xray_sdk.core import xray_recorder, patch_all
patch_all()


@xray_recorder.capture('lambda_handler')
def lambda_handler(event, context):
    """Process SQS batch events and detect conflicts"""
    
    print(f"📦 Received {len(event.get('Records', []))} messages")
    
    conflicts_detected = 0
    
    for record in event.get('Records', []):
        try:
            # Parse message body
            message_body = json.loads(record['body'])
            transaction = message_body.get('transaction', {})
            champion_decision = message_body.get('champion_decision', 'UNKNOWN')
            champion_risk_score = message_body.get('champion_risk_score', 0)
            
            user_id = transaction.get('user_id', 'unknown')
            amount = transaction.get('amount', 0)
            
            # ============================================
            # SIMULATE HEAVY DL MODEL (200ms)
            # ============================================
            
            time.sleep(0.2)  # Simulate expensive inference
            
            # Generate shadow decision (random for demo)
            # In production, this would be a real challenger model
            shadow_risk_score = random.uniform(0, 100)
            shadow_decision = "BLOCK" if shadow_risk_score > 75 else "ALLOW"
            
            # ============================================
            # CONFLICT DETECTION
            # ============================================
            
            if champion_decision != shadow_decision:
                conflicts_detected += 1
                print(f"⚠️ CONFLICT DETECTED: Champion [{champion_decision}] vs Shadow [{shadow_decision}]")
                print(f"   User: {user_id}, Amount: ${amount}")
                print(f"   Champion Risk: {champion_risk_score:.2f}, Shadow Risk: {shadow_risk_score:.2f}")
            else:
                print(f"✅ Agreement: Both models decided {champion_decision} for user {user_id}")
            
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    total_processed = len(event.get('Records', []))
    agreement_rate = ((total_processed - conflicts_detected) / total_processed * 100) if total_processed > 0 else 0
    
    print(f"\n📊 Shadow Processing Summary:")
    print(f"   Total Processed: {total_processed}")
    print(f"   Conflicts: {conflicts_detected}")
    print(f"   Agreement Rate: {agreement_rate:.1f}%")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': total_processed,
            'conflicts': conflicts_detected,
            'agreement_rate': round(agreement_rate, 2)
        })
    }
