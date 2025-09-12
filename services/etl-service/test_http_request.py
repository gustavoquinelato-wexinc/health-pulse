#!/usr/bin/env python3
"""
Test script to exactly mimic ETL HTTP request to backend
"""

import asyncio
import httpx
import sys
import os

# Add the ETL service to the path
sys.path.insert(0, os.path.dirname(__file__))

from app.jobs.orchestrator import _get_job_auth_token

async def test_http_request():
    """Test the exact HTTP request that ETL makes"""
    print("🧪 Testing ETL HTTP Request to Backend...")
    print("=" * 60)
    
    try:
        # Get auth token like ETL does
        auth_token = _get_job_auth_token(1)
        print(f"✅ Got auth token: {auth_token[:20]}...")
        
        # Prepare exact payload like ETL does
        entities = [{
            "entity_data": {
                "external_id": "12658",
                "key": "BDP", 
                "name": "Benefits Data Products",
                "project_type": "software"
            },
            "record_id": 12658,  # Integer
            "table_name": "projects"
        }]
        
        payload = {
            "entities": entities,
            "operation": "bulk_store"
        }
        
        print(f"📤 Payload: {payload}")
        
        # Prepare headers like ETL does
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = f"Bearer {auth_token}"
        
        # Make HTTP request like ETL does
        backend_url = os.getenv("BACKEND_SERVICE_URL", "http://localhost:3001")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{backend_url}/api/v1/ai/vectors/bulk",
                json=payload,
                headers=headers
            )
            
            print(f"📊 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"📊 Response: {result}")
                
                if result.get('success'):
                    vectors_stored = result.get('vectors_stored', 0)
                    vectors_failed = result.get('vectors_failed', 0)
                    
                    if vectors_stored > 0:
                        print(f"✅ SUCCESS: {vectors_stored} vectors stored!")
                    elif vectors_failed > 0:
                        print(f"❌ FAILED: {vectors_failed} vectors failed")
                    else:
                        print(f"⚠️  UNKNOWN: No vectors stored or failed")
                else:
                    print(f"❌ API Error: {result.get('error', 'Unknown error')}")
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_http_request())
