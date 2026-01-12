import json
import xgboost as xgb
import numpy as np
import random
import time

# Mimic Kaggle Credit Card Fraud Dataset Stats
# 284,807 transactions, 0.172% fraud
TOTAL_SAMPLES = 10000
FRAUD_RATIO = 0.0017
FEATURES = ['amount', 'velocity', 'time_diff', 'location_mismatch']

def generate_synthetic_data():
    """
    Generates synthetic data mirroring real financial patterns.
    - Legit: Low velocity, small amounts, inconsistent times.
    - Fraud: High velocity, high amounts or weird locations.
    """
    print(f"🧪 Generating {TOTAL_SAMPLES} synthetic transactions (Fraud Rate: {FRAUD_RATIO:.2%})...")
    
    X = []
    y = []
    
    for _ in range(TOTAL_SAMPLES):
        is_fraud = random.random() < FRAUD_RATIO
        
        if is_fraud:
            # Pattern: Fraud is fast, expensive, or far away
            velocity = random.randint(5, 20)      # High velocity
            amount = random.uniform(100, 2000)    # High amount
            time_diff = random.uniform(0, 5)      # Fast distinct txns
            loc_mismatch = 1                      # Different location
            y.append(1)
        else:
            # Pattern: Normal usage
            velocity = random.randint(0, 4)
            amount = random.uniform(5, 100)
            time_diff = random.uniform(60, 3600)
            loc_mismatch = 0 if random.random() > 0.05 else 1 # Rare mismatch
            y.append(0)
            
        X.append([amount, velocity, time_diff, loc_mismatch])
    
    return np.array(X), np.array(y)

import os
import pandas as pd # Requires pip install pandas

def load_data():
    """
    Load data from Kaggle CSV if present, else generate synthetic.
    """
    if os.path.exists('creditcard.csv'):
        print("📂 Found 'creditcard.csv'! Training on Real Kaggle Dataset...")
        df = pd.read_csv('creditcard.csv')
        
        # Kaggle Features: Time, V1..V28, Amount, Class
        # MAPPING STRATEGY: 
        # Since our API uses [Amount, Velocity, TimeDiff, LocMismatch], we map/engineer these.
        # This is a simplifcation for the Demo. 
        # real_features = df[['Amount', 'V1', 'V2', 'Class']] 
        
        # For this demo to work with the Champion Schema, we stick to Synthetic
        # UNLESS you update Champion to accept V1..V28.
        print("⚠️ NOTE: To use full Kaggle features, update champion_function.py TransactionPayload.")
        print("⚠️ FALLBACK: Generating synthetic data compatible with current API Schema.")
        return generate_synthetic_data()
        
    else:
        print("⚠️ 'creditcard.csv' not found. Using Synthetic Data (Kaggle Stats Mimic).")
        return generate_synthetic_data()

def train():
    X, y = load_data()
    
    print("🧠 Training XGBoost Model...")
    # scale_pos_weight is CRITICAL for imbalanced datasets (Kaggle context)
    model = xgb.XGBClassifier(
        max_depth=4,
        eta=0.2,
        objective='binary:logistic',
        scale_pos_weight=100  # Heavily penalize missing a fraud (since fraud is rare)
    )
    
    model.fit(X, y)
    
    # Evaluate
    preds = model.predict(X)
    accuracy = np.mean(preds == y)
    print(f"✅ Training Complete. Accuracy: {accuracy:.4f}")
    
    # Save for Lambda
    model.save_model("model.json")
    print("💾 Model saved to 'model.json'")

if __name__ == "__main__":
    train()
