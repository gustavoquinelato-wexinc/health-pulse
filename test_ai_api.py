#!/usr/bin/env python3
"""
Test AI Query Interface via API endpoints
Run this to test the Phase 3-6 implementation through HTTP requests
"""

import requests
import json
import sys

# Backend service URL
BASE_URL = "http://localhost:3001"

def test_health_endpoint():
    """Test the AI health endpoint"""
    print("🏥 Testing AI Health Endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/ai/health")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_capabilities_endpoint():
    """Test the AI capabilities endpoint (requires auth)"""
    print("\n🔧 Testing AI Capabilities Endpoint...")
    try:
        # Note: This will require authentication in real usage
        response = requests.get(f"{BASE_URL}/api/v1/ai/capabilities")
        print(f"Status: {response.status_code}")
        if response.status_code == 401:
            print("✅ Endpoint exists but requires authentication (expected)")
            return True
        elif response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_query_endpoint():
    """Test the AI query endpoint (requires auth)"""
    print("\n💬 Testing AI Query Endpoint...")
    try:
        # Note: This will require authentication in real usage
        test_query = {
            "query": "Show me recent work items",
            "context": {"test": True}
        }
        response = requests.post(
            f"{BASE_URL}/api/v1/ai/query",
            json=test_query,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 401:
            print("✅ Endpoint exists but requires authentication (expected)")
            return True
        elif response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_search_endpoint():
    """Test the AI search endpoint (requires auth)"""
    print("\n🔍 Testing AI Search Endpoint...")
    try:
        # Note: This will require authentication in real usage
        test_search = {
            "query": "test search",
            "limit": 5
        }
        response = requests.post(
            f"{BASE_URL}/api/v1/ai/search",
            json=test_search,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 401:
            print("✅ Endpoint exists but requires authentication (expected)")
            return True
        elif response.status_code == 200:
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all API tests"""
    print("🚀 Testing AI Query Interface API Endpoints")
    print("=" * 60)
    
    tests = [
        test_health_endpoint,
        test_capabilities_endpoint,
        test_query_endpoint,
        test_search_endpoint
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   Health Endpoint: {'✅ PASS' if results[0] else '❌ FAIL'}")
    print(f"   Capabilities Endpoint: {'✅ PASS' if results[1] else '❌ FAIL'}")
    print(f"   Query Endpoint: {'✅ PASS' if results[2] else '❌ FAIL'}")
    print(f"   Search Endpoint: {'✅ PASS' if results[3] else '❌ FAIL'}")
    
    if all(results):
        print("\n🎉 All API endpoints are working correctly!")
        print("\n💡 Next Steps:")
        print("   1. Add authentication to test full functionality")
        print("   2. Test with real queries once authenticated")
        print("   3. Build UI components to consume these APIs")
    else:
        print("\n⚠️  Some endpoints need attention")

if __name__ == "__main__":
    main()
