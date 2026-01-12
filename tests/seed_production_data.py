import boto3
import random
import time
from decimal import Decimal
from botocore.config import Config

# Configuration
TABLE_NAME = "sherlock_state"
REGION = "us-east-1"
NUM_USERS = 120

# Boto3 client with retry logic
config = Config(
   retries = {
      'max_attempts': 10,
      'mode': 'standard'
   }
)
dynamodb = boto3.resource('dynamodb', region_name=REGION, config=config)
table = dynamodb.Table(TABLE_NAME)

LOCATIONS = ["London", "New York", "Paris", "Singapore", "Tokyo", "Berlin", "Sydney", "Dubai", "Madrid", "Toronto"]
DECISIONS = ["ALLOW", "ALLOW", "ALLOW", "BLOCK"] # Weighted towards ALLOW

def generate_user_data(user_id):
    """Generate realistic production-like user data"""
    persona = random.choice(["standard", "standard", "traveler", "bot"])
    
    if persona == "standard":
        velocity = random.randint(1, 4)
        location = random.choice(LOCATIONS)
        decision = "ALLOW"
        risk_score = random.uniform(5, 45)
    elif persona == "traveler":
        velocity = random.randint(2, 5)
        location = random.choice(LOCATIONS)
        decision = "ALLOW"
        risk_score = random.uniform(30, 60)
    else: # bot
        velocity = random.randint(8, 25)
        location = random.choice(LOCATIONS)
        decision = "BLOCK"
        risk_score = random.uniform(85, 99)

    current_time = int(time.time())
    ttl = current_time + 3600 # Keep for 1 hour to ensure it's visible in scan
    
    return {
        'user_id': user_id,
        'velocity_counter': velocity,
        'last_location': location,
        'last_decision': decision,
        'last_risk_score': Decimal(str(round(risk_score, 2))),
        'last_transaction_id': f"seed_txn_{random.randint(100000, 999999)}",
        'ttl_window': ttl
    }

def seed_data():
    print(f"🚀 Seeding {NUM_USERS} user profiles into {TABLE_NAME}...")
    
    with table.batch_writer() as batch:
        for i in range(NUM_USERS):
            user_id = f"user_{1000 + i}"
            item = generate_user_data(user_id)
            batch.put_item(Item=item)
            if (i + 1) % 20 == 0:
                print(f"✅ Synced {i + 1} users...")

    print("\n✨ Seeding Complete!")
    print(f"   Table: {TABLE_NAME}")
    print(f"   Users: {NUM_USERS}")

if __name__ == "__main__":
    try:
        seed_data()
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
