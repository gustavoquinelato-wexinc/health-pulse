#!/usr/bin/env python3
"""
Test script to verify if backend service has our fix
"""

import asyncio
import httpx
import sys
import os

# Add the ETL service to the path
sys.path.insert(0, os.path.dirname(__file__))

from app.jobs.orchestrator import _get_job_auth_token

async def test_backend_fix():
    """Test if backend service has our text content fix"""
    print("🧪 Testing if Backend Service has our fix...")
    print("=" * 60)
    
    try:
        # Get auth token
        auth_token = _get_job_auth_token(1)
        print(f"✅ Got auth token: {auth_token[:20]}...")
        
        # Test with entity that should definitely create text content
        # Using only string values to ensure text_parts is not empty
        entities = [{
            "entity_data": {
                "key": "TEST-STRING-ONLY",
                "name": "Test String Only Project", 
                "description": "This should definitely create text content"
            },
            "record_id": 77777,
            "table_name": "projects"
        }]
        
        payload = {
            "entities": entities,
            "operation": "bulk_store"
        }
        
        print(f"📤 Testing with string-only entity data...")
        print(f"Entity data: {entities[0]['entity_data']}")
        
        # Make HTTP request
        backend_url = os.getenv("BACKEND_SERVICE_URL", "http://localhost:3001")
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = f"Bearer {auth_token}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{backend_url}/api/v1/ai/vectors/bulk",
                json=payload,
                headers=headers
            )
            
            print(f"📊 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"📊 Response: {result}")
                
                success = result.get('success', False)
                vectors_stored = result.get('vectors_stored', 0)
                vectors_failed = result.get('vectors_failed', 0)
                provider_used = result.get('provider_used', 'unknown')
                
                if success and vectors_stored > 0:
                    print(f"✅ SUCCESS: Backend service has our fix!")
                    print(f"   - {vectors_stored} vectors stored")
                    print(f"   - Provider: {provider_used}")
                    print(f"   - Text content generation is working")
                elif vectors_failed > 0:
                    print(f"❌ FAILED: Backend service may not have our fix")
                    print(f"   - {vectors_failed} vectors failed")
                    print(f"   - Text content generation may still be broken")
                    print(f"   - Backend service may need restart to pick up changes")
                else:
                    print(f"⚠️  UNKNOWN: Unexpected result")
                    
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_backend_fix())
