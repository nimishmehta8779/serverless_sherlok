import requests
import json
import uuid
import time
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
API_ENDPOINT = "https://fkijxo8fxi.execute-api.us-east-1.amazonaws.com/transaction"
USER_ID = f"linkedin_demo_{int(time.time())}"
API_KEY = "sherlock_secure_2026_prod"

# Authenticated Client
client = requests.Session()
client.headers.update({
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
})

def print_result(title, response):
    print(f"\n🔹 {title}")
    print(f"Status Code: {response.status_code}")
    try:
        data = response.json()
        print(f"Decision: {data.get('status')} | Risk Score: {data.get('risk_score')} | Latency: {data.get('latency_ms')}ms")
        if data.get('idempotent'):
            print("✨ IDEMPOTENCY HIT: Prevented duplicate processing!")
        if data.get('reasons'):
            print(f"Reasons: {data.get('reasons')}")
    except:
        print(f"Body: {response.text}")

def run_suite():
    print(f"🚀 Starting Sherlock Production Validation Suite")
    print(f"Testing User: {USER_ID}\n" + "="*50)

    # 1. Pydantic Validation Check
    print_result("TEST 1: Schema Validation (Negative Amount)", 
                 client.post(API_ENDPOINT, json={"user_id": USER_ID, "amount": -100, "transaction_id": "val_1"}))

    # 2. Path to Happy Path (Normal Tx)
    txn_id_1 = str(uuid.uuid4())
    print_result("TEST 2: Happy Path Transaction", 
                 client.post(API_ENDPOINT, json={
                     "user_id": USER_ID, 
                     "amount": 50.0, 
                     "merchant": "Apple Store",
                     "transaction_id": txn_id_1,
                     "location": "London"
                 }))

    # 3. Idempotency Check (The "Secret Sauce")
    print_result("TEST 3: Idempotency (Replaying same Transaction ID)", 
                 client.post(API_ENDPOINT, json={
                     "user_id": USER_ID, 
                     "amount": 50.0, 
                     "merchant": "Apple Store",
                     "transaction_id": txn_id_1, # SAME ID
                     "location": "London"
                 }))

    # 4. Velocity Check (Rapid Fire)
    print("\n🔹 TEST 4: High Velocity Detection (Spamming 5 requests)")
    for i in range(5):
        client.post(API_ENDPOINT, json={
            "user_id": USER_ID, 
            "amount": 20.0, 
            "merchant": f"Store_{i}",
            "transaction_id": str(uuid.uuid4()),
            "location": "London"
        })
    
    print_result("Final Velocity Check (Should be BLOCKED)", 
                 client.post(API_ENDPOINT, json={
                     "user_id": USER_ID, 
                     "amount": 20.0, 
                     "merchant": "Final Store",
                     "transaction_id": str(uuid.uuid4()),
                     "location": "London"
                 }))

    # 5. Impossible Travel Check
    print_result("TEST 5: Impossible Travel (London -> Tokyo in 1 second)", 
                 client.post(API_ENDPOINT, json={
                     "user_id": USER_ID, 
                     "amount": 10.0, 
                     "merchant": "Sake Bar",
                     "transaction_id": str(uuid.uuid4()),
                     "location": "Tokyo" # CHANGED LOCATION
                 }))

    # 6. Graph Analysis (Fraud Ring)
    print("\n🔹 TEST 6: Fraud Ring Detection (device_666 used by many distinct users)")
    device_id = "device_666"
    for i in range(1, 6): # 5 distinct users
        print(f"   Simulating User_{i} on {device_id}...")
        resp = client.post(API_ENDPOINT, json={
            "user_id": f"ring_user_{i}_{int(time.time())}", 
            "amount": 15.0, 
            "merchant": "Graph Test",
            "transaction_id": str(uuid.uuid4()),
            "location": "London",
            "device_id": device_id
        })
        if i >= 4: # The 4th and 5th users should trigger the ring detection
             print_result(f"User {i} (Should be BLOCKED as RING)", resp)

if __name__ == "__main__":
    run_suite()
