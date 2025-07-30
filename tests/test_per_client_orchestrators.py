#!/usr/bin/env python3
"""
Test script to verify multi-instance ETL setup is working correctly.

This script tests the simplified multi-instance approach where:
- Each ETL instance serves only one client
- No complex cross-client orchestrator logic
- Simple, clean, and maintainable code
"""

import requests
import time

def test_multi_instance_setup():
    """Test multi-instance ETL setup."""

    print("🧪 Testing Multi-Instance ETL Setup")
    print("=" * 50)

    # Test endpoints for both ETL instances
    wex_base_url = "http://localhost:8000"
    techcorp_base_url = "http://localhost:8001"

    print("\n📋 Step 1: Testing WEX ETL Instance (Port 8000)")
    test_etl_instance("WEX", wex_base_url)

    print("\n📋 Step 2: Testing TechCorp ETL Instance (Port 8001)")
    test_etl_instance("TechCorp", techcorp_base_url)

    print("\n✅ Multi-Instance Test Complete!")
    print("\n🎯 Expected Results:")
    print("  • WEX ETL instance serves only WEX client data")
    print("  • TechCorp ETL instance serves only TechCorp client data")
    print("  • Each instance has independent orchestrator")
    print("  • No cross-client interference")
    print("  • Much simpler code and architecture")

def test_etl_instance(client_name, base_url):
    """Test a specific ETL instance."""

    try:
        # Test health endpoint
        print(f"  🔍 Testing {client_name} health endpoint...")
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print(f"    ✅ {client_name} ETL instance is healthy")
        else:
            print(f"    ❌ {client_name} ETL instance health check failed")
            return

        # Test orchestrator status (requires auth, so expect 401)
        print(f"  🔍 Testing {client_name} orchestrator endpoint...")
        response = requests.get(f"{base_url}/api/v1/orchestrator/status", timeout=5)
        if response.status_code == 401:
            print(f"    ✅ {client_name} orchestrator endpoint responding (auth required)")
        else:
            print(f"    ⚠️ {client_name} orchestrator endpoint unexpected response: {response.status_code}")

        # Test job status endpoint (requires auth, so expect 401)
        print(f"  🔍 Testing {client_name} job status endpoint...")
        response = requests.get(f"{base_url}/api/v1/jobs/status", timeout=5)
        if response.status_code == 401:
            print(f"    ✅ {client_name} job status endpoint responding (auth required)")
        else:
            print(f"    ⚠️ {client_name} job status endpoint unexpected response: {response.status_code}")

    except requests.exceptions.ConnectionError:
        print(f"    ❌ Cannot connect to {client_name} ETL instance at {base_url}")
        print(f"    💡 Make sure the {client_name} ETL instance is running")
    except requests.exceptions.Timeout:
        print(f"    ❌ {client_name} ETL instance timeout")
    except Exception as e:
        print(f"    ❌ {client_name} ETL instance test error: {e}")

if __name__ == "__main__":
    test_multi_instance_setup()
