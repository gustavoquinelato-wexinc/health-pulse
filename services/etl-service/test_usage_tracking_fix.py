#!/usr/bin/env python3
"""
Test script to verify the AIUsageTracking processing_time fix
"""

import asyncio
import httpx
import sys
import os

# Add the ETL service to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend-service'))

async def test_usage_tracking_fix():
    """Test that the processing_time error is fixed"""
    
    print("🧪 Testing AIUsageTracking processing_time fix...")
    
    # Test data - single project
    test_data = {
        "operation": "bulk_store",
        "entities": [
            {
                "entity_data": {
                    "external_id": "99999",
                    "key": "TEST",
                    "name": "Test Project",
                    "project_type": "software"
                },
                "record_id": 99999,
                "table_name": "projects"
            }
        ]
    }
    
    try:
        # Make request to backend
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First login to get auth token
            login_response = await client.post(
                "http://localhost:3001/auth/login",
                json={
                    "email": "admin@pulse.com",
                    "password": "admin123"
                }
            )
            
            if login_response.status_code != 200:
                print(f"❌ Login failed: {login_response.status_code}")
                return
                
            print("✅ Login successful")
            
            # Get auth token from cookies
            auth_token = None
            for cookie in login_response.cookies:
                if cookie.name == "session_token":
                    auth_token = cookie.value
                    break
            
            if not auth_token:
                print("❌ No auth token found in cookies")
                return
                
            print(f"✅ Auth token obtained: {auth_token[:20]}...")
            
            # Make vectorization request
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            }
            
            print("🚀 Sending vectorization request...")
            response = await client.post(
                "http://localhost:3001/api/v1/ai/vectors/bulk",
                json=test_data,
                headers=headers
            )
            
            print(f"📊 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success! Result: {result}")
                
                if result.get('vectors_stored', 0) > 0:
                    print("🎉 Vector stored successfully - processing_time error is FIXED!")
                else:
                    print("⚠️ No vectors stored, but no processing_time error")
                    
            else:
                print(f"❌ Request failed: {response.text}")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_usage_tracking_fix())
