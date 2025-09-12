#!/usr/bin/env python3
"""
Test script to verify the backend vectorization queue processing is working correctly.
This script directly tests the backend queue processing without going through the ETL trigger.
"""

import asyncio
import sys
import os
import httpx
import json
from datetime import datetime

# Add the backend service to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services', 'backend-service'))

async def test_backend_vectorization():
    """Test the backend vectorization queue processing directly."""
    
    print("🧪 Testing Backend Vectorization Queue Processing...")
    
    try:
        # Test 1: Import the backend modules
        print("\n1️⃣ Testing imports...")
        from app.api.ai_config_routes import process_tenant_vectorization_queue
        from app.core.database import get_database
        from app.models.unified_models import VectorizationQueue
        print("✅ Backend modules imported successfully")
        
        # Test 2: Check database connection
        print("\n2️⃣ Testing database connection...")
        database = get_database()
        with database.get_write_session_context() as session:
            # Check if vectorization queue table exists and has data
            total_items = session.query(VectorizationQueue).count()
            pending_items = session.query(VectorizationQueue).filter(
                VectorizationQueue.status == 'pending'
            ).count()
            print(f"✅ Database connected - Total queue items: {total_items}, Pending: {pending_items}")
        
        # Test 3: Check for pending items for tenant 1
        print("\n3️⃣ Checking queue status for tenant 1...")
        with database.get_write_session_context() as session:
            tenant_1_total = session.query(VectorizationQueue).filter(
                VectorizationQueue.tenant_id == 1
            ).count()
            
            tenant_1_pending = session.query(VectorizationQueue).filter(
                VectorizationQueue.status == 'pending',
                VectorizationQueue.tenant_id == 1
            ).count()
            
            print(f"✅ Tenant 1 queue status - Total: {tenant_1_total}, Pending: {tenant_1_pending}")
            
            if tenant_1_pending > 0:
                # Show sample pending items
                sample_items = session.query(VectorizationQueue).filter(
                    VectorizationQueue.status == 'pending',
                    VectorizationQueue.tenant_id == 1
                ).limit(3).all()
                
                print(f"📋 Sample pending items:")
                for item in sample_items:
                    print(f"   - ID: {item.id}, Table: {item.table_name}, Record: {item.record_db_id}")
        
        # Test 4: Test the queue processing function directly
        if tenant_1_pending > 0:
            print("\n4️⃣ Testing queue processing function directly...")
            try:
                await process_tenant_vectorization_queue(tenant_id=1, batch_size=5)
                print("✅ Queue processing function executed successfully")
            except Exception as e:
                print(f"❌ Queue processing failed: {e}")
                print(f"Error type: {type(e).__name__}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
        else:
            print("\n4️⃣ No pending items to process for tenant 1")
        
        # Test 5: Test HTTP endpoint (if backend is running)
        print("\n5️⃣ Testing HTTP endpoint...")
        try:
            # First, try to get a token (simulate system authentication)
            async with httpx.AsyncClient() as client:
                # Try to call the endpoint (this will fail without proper auth, but we can see if it's reachable)
                response = await client.post(
                    "http://localhost:3001/api/v1/ai/vectors/process-queue",
                    json={"tenant_id": 1},
                    headers={"Authorization": "Bearer test-token"},
                    timeout=5.0
                )
                print(f"✅ Backend endpoint reachable - Status: {response.status_code}")
                if response.status_code != 200:
                    print(f"   Response: {response.text}")
        except httpx.ConnectError:
            print("⚠️  Backend service not running on localhost:3001")
        except Exception as e:
            print(f"⚠️  Backend endpoint test failed: {e}")
        
        print("\n✅ Backend vectorization test completed!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this from the project root directory")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_backend_vectorization())
