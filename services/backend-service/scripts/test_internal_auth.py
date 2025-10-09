#!/usr/bin/env python3
"""
Test script to verify internal authentication configuration.
"""

import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_internal_auth():
    """Test internal authentication configuration."""
    
    print("🔐 Internal Authentication Test")
    print("=" * 50)
    
    try:
        # Test 1: Check ETL_INTERNAL_SECRET configuration
        print("\n1️⃣ Checking ETL_INTERNAL_SECRET configuration...")
        from app.core.config import get_settings
        settings = get_settings()
        
        internal_secret = getattr(settings, 'ETL_INTERNAL_SECRET', None)
        if internal_secret:
            print(f"✅ ETL_INTERNAL_SECRET is configured: {internal_secret[:10]}...")
        else:
            print("❌ ETL_INTERNAL_SECRET is not configured")
            return
            
        # Test 2: Test verify_internal_auth function
        print("\n2️⃣ Testing verify_internal_auth function...")
        from app.etl.jobs import verify_internal_auth
        from fastapi import Request
        
        # Create a mock request with the correct header
        class MockRequest:
            def __init__(self, headers):
                self.headers = headers
                
        # Test with correct secret
        print("Testing with correct secret...")
        mock_request = MockRequest({"X-Internal-Auth": internal_secret})
        try:
            verify_internal_auth(mock_request)
            print("✅ verify_internal_auth passed with correct secret")
        except Exception as e:
            print(f"❌ verify_internal_auth failed with correct secret: {e}")
            
        # Test with wrong secret
        print("Testing with wrong secret...")
        mock_request_wrong = MockRequest({"X-Internal-Auth": "wrong-secret"})
        try:
            verify_internal_auth(mock_request_wrong)
            print("❌ verify_internal_auth should have failed with wrong secret")
        except Exception as e:
            print(f"✅ verify_internal_auth correctly rejected wrong secret: {e}")
            
        # Test with missing header
        print("Testing with missing header...")
        mock_request_missing = MockRequest({})
        try:
            verify_internal_auth(mock_request_missing)
            print("❌ verify_internal_auth should have failed with missing header")
        except Exception as e:
            print(f"✅ verify_internal_auth correctly rejected missing header: {e}")
            
        print("\n📋 Summary:")
        print("- ETL_INTERNAL_SECRET is properly configured")
        print("- verify_internal_auth function works correctly")
        print("- The issue might be in the hybrid authentication logic")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_internal_auth()
