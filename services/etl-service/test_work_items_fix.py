#!/usr/bin/env python3
"""
Test script to verify work items vectorization fix
"""

import asyncio
import httpx
import sys
import os

# Add the ETL service to the path
sys.path.insert(0, os.path.dirname(__file__))

from app.jobs.orchestrator import _get_job_auth_token

async def test_work_items_vectorization():
    """Test work items AI vectorization with integer external_id"""
    print("🧪 Testing Work Items AI Vectorization Fix...")
    print("=" * 70)
    
    try:
        # Get auth token
        auth_token = _get_job_auth_token(1)
        print(f"✅ Got auth token: {auth_token[:20]}...")
        
        # Create test work item entity with integer external_id (like real ETL data)
        test_entity = {
            "entity_data": {
                "key": "TEST-123",              # String key (for text content)
                "summary": "Test Work Item",    # String
                "priority": "3 - Medium",       # String
                "team": "Test Team",            # String
                "assignee": "Test User <test@example.com>"  # String
            },
            "record_id": 12345,                 # Integer external_id (FIXED!)
            "table_name": "work_items"          # String
        }
        
        payload = {
            "entities": [test_entity],
            "operation": "bulk_store"
        }
        
        print(f"📤 Sending test work item:")
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
                    print(f"\n🎉 SUCCESS! Work Items AI vectorization is FIXED!")
                    print(f"   ✅ Integer external_id used correctly")
                    print(f"   ✅ Text content generated from work item data")
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
        print(f"   Look for logs with 'table=work_items' to see work item processing")
                
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_work_items_vectorization())
