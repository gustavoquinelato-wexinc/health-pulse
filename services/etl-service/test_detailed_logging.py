#!/usr/bin/env python3
"""
Test script to trigger detailed ETL logging in backend
"""

import asyncio
import httpx
import sys
import os

# Add the ETL service to the path
sys.path.insert(0, os.path.dirname(__file__))

from app.jobs.orchestrator import _get_job_auth_token

async def test_with_detailed_logging():
    """Test ETL AI vectorization with detailed backend logging"""
    print("🧪 Testing ETL AI Vectorization with Detailed Logging...")
    print("=" * 70)
    
    try:
        # Get auth token
        auth_token = _get_job_auth_token(1)
        print(f"✅ Got auth token: {auth_token[:20]}...")
        
        # Create test entity with mixed data types (like real ETL data)
        test_entity = {
            "entity_data": {
                "external_id": "12345",      # String (from API)
                "key": "TEST-PROJECT",       # String
                "name": "Test Project Name", # String
                "project_type": "software",  # String
                "active": True,              # Boolean
                "priority": 3                # Integer
            },
            "record_id": 12345,              # Integer (like real ETL)
            "table_name": "projects"         # String
        }
        
        payload = {
            "entities": [test_entity],
            "operation": "bulk_store"
        }
        
        print(f"📤 Sending test entity:")
        print(f"   Entity data: {test_entity['entity_data']}")
        print(f"   Record ID: {test_entity['record_id']} (type: {type(test_entity['record_id'])})")
        print(f"   Table: {test_entity['table_name']}")
        
        # Make HTTP request
        backend_url = os.getenv("BACKEND_SERVICE_URL", "http://localhost:3001")
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = f"Bearer {auth_token}"
        
        print(f"\n📡 Making request to: {backend_url}/api/v1/ai/vectors/bulk")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{backend_url}/api/v1/ai/vectors/bulk",
                json=payload,
                headers=headers
            )
            
            print(f"\n📊 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"📊 Response: {result}")
                
                success = result.get('success', False)
                vectors_stored = result.get('vectors_stored', 0)
                vectors_failed = result.get('vectors_failed', 0)
                provider_used = result.get('provider_used', 'unknown')
                
                print(f"\n📈 Results Summary:")
                print(f"   Success: {success}")
                print(f"   Vectors stored: {vectors_stored}")
                print(f"   Vectors failed: {vectors_failed}")
                print(f"   Provider used: {provider_used}")
                
                if success and vectors_stored > 0:
                    print(f"\n🎉 SUCCESS! ETL AI vectorization is working!")
                    print(f"   ✅ Text content generated correctly")
                    print(f"   ✅ Embedding created successfully")
                    print(f"   ✅ Vector stored in Qdrant")
                    print(f"   ✅ Bridge record created in PostgreSQL")
                elif vectors_failed > 0:
                    print(f"\n❌ FAILED: {vectors_failed} vectors failed")
                    print(f"   Check backend logs for detailed error information")
                else:
                    print(f"\n⚠️  UNKNOWN: No vectors stored or failed")
                    
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        print(f"\n📋 Check backend service logs for detailed [ETL_REQUEST] entries")
        print(f"   Look for logs starting with '[ETL_REQUEST]' to see step-by-step processing")
                
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_with_detailed_logging())
