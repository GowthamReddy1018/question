#!/usr/bin/env python3
"""
Full test script to verify the FastAPI endpoints work correctly
"""

import requests
import json

def test_api_endpoints():
    """Test the FastAPI endpoints"""
    base_url = "http://localhost:8000"
    
    print("Testing FastAPI Endpoints...")
    print("=" * 50)
    
    try:
        # Test root endpoint
        print("1. Testing root endpoint...")
        response = requests.get(f"{base_url}/")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        print()
        
        # Test health endpoint
        print("2. Testing health endpoint...")
        response = requests.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        print()
        
        # Test generate endpoint with sample Telugu text
        print("3. Testing generate endpoint...")
        sample_text = "తెలంగాణ రాష్ట్రం 2014 లో ఏర్పడింది. హైదరాబాద్ ఈ రాష్ట్ర రాజధాని."
        
        payload = {"text": sample_text}
        response = requests.post(
            f"{base_url}/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data['success']}")
            print(f"   Message: {data['message']}")
            print(f"   Q&A Pairs: {len(data['qa_pairs'])}")
            
            for i, qa in enumerate(data['qa_pairs'], 1):
                print(f"     {i}. Q: {qa['question']}")
                print(f"        A: {qa['answer']}")
        else:
            print(f"   Error: {response.text}")
        print()
        
        # Test with invalid input
        print("4. Testing with invalid input...")
        payload = {"text": "short"}
        response = requests.post(
            f"{base_url}/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Success: {data['success']}")
        print(f"   Error: {data['error']}")
        print()
        
        # Test with empty input
        print("5. Testing with empty input...")
        payload = {"text": ""}
        response = requests.post(
            f"{base_url}/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Success: {data['success']}")
        print(f"   Error: {data['error']}")
        print()
        
        # Test with non-Telugu input
        print("6. Testing with non-Telugu input...")
        payload = {"text": "This is English text only."}
        response = requests.post(
            f"{base_url}/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        
        print(f"   Status: {response.status_code}")
        data = response.json()
        print(f"   Success: {data['success']}")
        print(f"   Error: {data['error']}")
        print()
        
        # Test with long input
        print("7. Testing with long input...")
        long_text = " ".join(["తెలంగాణ రాష్ట్రం 2014 లో ఏర్పడింది."] * 50)  # Repeat to make it long
        payload = {"text": long_text}
        response = requests.post(
            f"{base_url}/generate",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data['success']}")
            print(f"   Message: {data['message']}")
            print(f"   Q&A Pairs: {len(data['qa_pairs'])}")
        else:
            print(f"   Error: {response.text}")
        print()
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the server. Make sure the server is running on http://localhost:8000")
        print("   Start the server with: py -m uvicorn app:app --reload --host 0.0.0.0 --port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_api_endpoints()
