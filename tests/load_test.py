"""
Load Testing Script for Sherlock API
Simulates 50 concurrent users with various fraud scenarios
"""

import json
import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import sys


# Test data
USERS = [f'user_{i:03d}' for i in range(1, 21)]  # 20 unique users
LOCATIONS = ['New York', 'London', 'Tokyo', 'Paris', 'Sydney', 'Mumbai', 'Toronto', 'Berlin']
MERCHANTS = ['Amazon', 'Walmart', 'Target', 'Starbucks', 'Apple', 'Nike', 'Best Buy', 'Costco']


def generate_transaction(scenario='random'):
    """Generate a transaction based on scenario"""
    
    if scenario == 'clean':
        # Normal transaction - same user, same location
        user_id = random.choice(USERS)
        location = random.choice(LOCATIONS)
        
    elif scenario == 'impossible_travel':
        # Same user, different location (triggers impossible travel)
        user_id = random.choice(USERS)
        location = random.choice(LOCATIONS)
        
    elif scenario == 'high_velocity':
        # Same user repeatedly (triggers velocity check)
        user_id = USERS[0]  # Use same user
        location = LOCATIONS[0]
        
    else:  # random
        user_id = random.choice(USERS)
        location = random.choice(LOCATIONS)
    
    return {
        'user_id': user_id,
        'amount': round(random.uniform(10, 1000), 2),
        'location': location,
        'merchant': random.choice(MERCHANTS),
        'transaction_id': f'load_test_{int(time.time() * 1000)}_{random.randint(1000, 9999)}'
    }


def send_transaction(api_url, transaction):
    """Send a single transaction and measure latency"""
    start_time = time.time()
    
    try:
        response = requests.post(
            api_url,
            json=transaction,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        latency = (time.time() - start_time) * 1000  # Convert to ms
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'latency': latency,
                'decision': result.get('status'),
                'risk_score': result.get('risk_score'),
                'server_latency': result.get('latency_ms'),
                'user_id': transaction['user_id']
            }
        else:
            return {
                'success': False,
                'latency': latency,
                'error': response.text
            }
            
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        return {
            'success': False,
            'latency': latency,
            'error': str(e)
        }


def run_load_test(api_url, num_requests=100, num_workers=50):
    """Run concurrent load test"""
    
    print("=" * 70)
    print("🚀 Sherlock Load Test")
    print("=" * 70)
    print(f"API URL: {api_url}")
    print(f"Total Requests: {num_requests}")
    print(f"Concurrent Workers: {num_workers}")
    print()
    
    # Generate scenarios
    scenarios = []
    for i in range(num_requests):
        if i < 20:
            scenario = 'clean'
        elif i < 40:
            scenario = 'impossible_travel'
        elif i < 60:
            scenario = 'high_velocity'
        else:
            scenario = 'random'
        scenarios.append(scenario)
    
    random.shuffle(scenarios)
    
    # Generate transactions
    transactions = [generate_transaction(s) for s in scenarios]
    
    # Execute concurrent requests
    results = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(send_transaction, api_url, txn) for txn in transactions]
        
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            
            if completed % 10 == 0:
                print(f"Progress: {completed}/{num_requests} requests completed...")
    
    total_time = time.time() - start_time
    
    # Analyze results
    print("\n" + "=" * 70)
    print("📊 Load Test Results")
    print("=" * 70)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"\n✅ Success Rate: {len(successful)}/{num_requests} ({len(successful)/num_requests*100:.1f}%)")
    print(f"❌ Failed: {len(failed)}")
    
    if successful:
        latencies = [r['latency'] for r in successful]
        server_latencies = [r.get('server_latency', 0) for r in successful]
        
        print(f"\n⏱️  Latency Statistics (Total Round-Trip):")
        print(f"   Average: {sum(latencies)/len(latencies):.2f}ms")
        print(f"   Min: {min(latencies):.2f}ms")
        print(f"   Max: {max(latencies):.2f}ms")
        print(f"   P50: {sorted(latencies)[len(latencies)//2]:.2f}ms")
        print(f"   P95: {sorted(latencies)[int(len(latencies)*0.95)]:.2f}ms")
        print(f"   P99: {sorted(latencies)[int(len(latencies)*0.99)]:.2f}ms")
        
        print(f"\n⚡ Server-Side Latency (Lambda only):")
        print(f"   Average: {sum(server_latencies)/len(server_latencies):.2f}ms")
        print(f"   Min: {min(server_latencies):.2f}ms")
        print(f"   Max: {max(server_latencies):.2f}ms")
        
        # Decision distribution
        decisions = defaultdict(int)
        for r in successful:
            decisions[r.get('decision', 'UNKNOWN')] += 1
        
        print(f"\n🎯 Decision Distribution:")
        for decision, count in decisions.items():
            print(f"   {decision}: {count} ({count/len(successful)*100:.1f}%)")
        
        # Risk score distribution
        risk_scores = [r.get('risk_score', 0) for r in successful]
        print(f"\n📈 Risk Score Statistics:")
        print(f"   Average: {sum(risk_scores)/len(risk_scores):.2f}")
        print(f"   Min: {min(risk_scores):.2f}")
        print(f"   Max: {max(risk_scores):.2f}")
    
    print(f"\n⏱️  Total Test Duration: {total_time:.2f}s")
    print(f"📊 Throughput: {num_requests/total_time:.2f} requests/second")
    
    if failed:
        print(f"\n❌ Failed Requests:")
        for i, r in enumerate(failed[:5], 1):
            print(f"   {i}. {r.get('error', 'Unknown error')}")
        if len(failed) > 5:
            print(f"   ... and {len(failed)-5} more")
    
    print("\n" + "=" * 70)
    
    # Performance check
    if successful:
        avg_server_latency = sum(server_latencies) / len(server_latencies)
        if avg_server_latency < 50:
            print("✅ PERFORMANCE TARGET MET: Average server latency < 50ms")
        else:
            print(f"⚠️  PERFORMANCE WARNING: Average server latency {avg_server_latency:.2f}ms > 50ms target")
    
    print("=" * 70)


def main():
    if len(sys.argv) < 2:
        print("Usage: python load_test.py <api_url> [num_requests] [num_workers]")
        print("\nExample:")
        print("  python load_test.py https://abc123.execute-api.us-east-1.amazonaws.com/transaction")
        print("  python load_test.py https://abc123.execute-api.us-east-1.amazonaws.com/transaction 200 50")
        sys.exit(1)
    
    api_url = sys.argv[1]
    num_requests = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    num_workers = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    
    run_load_test(api_url, num_requests, num_workers)


if __name__ == '__main__':
    main()
