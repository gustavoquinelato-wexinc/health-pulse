#!/usr/bin/env python3
"""
Test script to verify authentication endpoints and token validation.
"""

import os
import sys
import asyncio
import httpx

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_auth_endpoints():
    """Test authentication endpoints and token validation."""
    
    print("🔐 Authentication Endpoints Test")
    print("=" * 50)
    
    backend_url = "http://localhost:3001"
    
    try:
        async with httpx.AsyncClient() as client:
            # Test 1: Health check
            print("\n1️⃣ Testing backend health...")
            try:
                response = await client.get(f"{backend_url}/health")
                if response.status_code == 200:
                    print("✅ Backend service is running")
                else:
                    print(f"❌ Backend health check failed: {response.status_code}")
                    return
            except Exception as e:
                print(f"❌ Cannot connect to backend service: {e}")
                return
                
            # Test 2: Test ETL jobs endpoint without auth
            print("\n2️⃣ Testing ETL jobs endpoint without authentication...")
            try:
                response = await client.get(f"{backend_url}/app/etl/jobs?tenant_id=1")
                print(f"Status: {response.status_code}")
                if response.status_code == 401:
                    print("✅ Correctly returns 401 Unauthorized (authentication required)")
                else:
                    print(f"⚠️ Unexpected status code: {response.status_code}")
                    print(f"Response: {response.text[:200]}")
            except Exception as e:
                print(f"❌ Error testing ETL endpoint: {e}")
                
            # Test 3: Try to login with system credentials
            print("\n3️⃣ Testing system login...")
            try:
                login_data = {
                    "email": "admin@example.com",
                    "password": "admin123"
                }
                response = await client.post(f"{backend_url}/auth/login", json=login_data)
                print(f"Login status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("token"):
                        token = data["token"]
                        print("✅ Login successful, token received")
                        print(f"Token preview: {token[:30]}...")
                        
                        # Test 4: Test ETL jobs endpoint with auth
                        print("\n4️⃣ Testing ETL jobs endpoint with authentication...")
                        headers = {"Authorization": f"Bearer {token}"}
                        response = await client.get(f"{backend_url}/app/etl/jobs?tenant_id=1", headers=headers)
                        print(f"Authenticated request status: {response.status_code}")
                        
                        if response.status_code == 200:
                            data = response.json()
                            print(f"✅ Successfully retrieved {len(data)} jobs")
                            for job in data:
                                print(f"   - {job.get('job_name')} (Status: {job.get('status')})")
                        else:
                            print(f"❌ Authenticated request failed: {response.status_code}")
                            print(f"Response: {response.text[:200]}")
                            
                    else:
                        print("❌ Login response missing token")
                        print(f"Response: {response.text[:200]}")
                else:
                    print(f"❌ Login failed: {response.status_code}")
                    print(f"Response: {response.text[:200]}")
                    
            except Exception as e:
                print(f"❌ Error during login test: {e}")
                
            # Test 5: Check if auth service is running
            print("\n5️⃣ Testing auth service connectivity...")
            try:
                auth_service_url = "http://localhost:4000"
                response = await client.get(f"{auth_service_url}/health")
                if response.status_code == 200:
                    print("✅ Auth service is running")
                else:
                    print(f"⚠️ Auth service health check: {response.status_code}")
            except Exception as e:
                print(f"❌ Auth service not accessible: {e}")
                print("💡 This might be why token validation is failing")
                
        print("\n📋 Summary:")
        print("- If login works but ETL endpoints fail, check token validation")
        print("- If auth service is down, start it with: cd services/auth-service && python -m uvicorn app.main:app --port 4000")
        print("- Frontend should store token in localStorage as 'pulse_token'")
        print("- Frontend should send token as 'Authorization: Bearer <token>' header")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_auth_endpoints())
