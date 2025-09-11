#!/usr/bin/env python3
"""
Test script for Phase 3-4 ETL AI Integration

This script tests the complete ETL → Backend → Qdrant integration flow:
1. Backend Service AI endpoints (/api/v1/ai/vectors/store, /api/v1/ai/vectors/search)
2. ETL Service AI Client enhancements
3. Vector storage and search functionality
"""

import asyncio
import httpx
import json
import sys
import os

# Add the services to the Python path
sys.path.append('services/backend-service')
sys.path.append('services/etl-service')

async def test_backend_service_health():
    """Test Backend Service health endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:3001/api/v1/health")
            if response.status_code == 200:
                print("✅ Backend Service is running")
                return True
            else:
                print(f"❌ Backend Service health check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Cannot connect to Backend Service: {e}")
        return False

async def test_ai_embeddings_endpoint():
    """Test the existing AI embeddings endpoint"""
    try:
        payload = {
            "texts": ["This is a test issue for AI integration", "Another test text for embedding"]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:3001/api/v1/ai/embeddings",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print(f"✅ AI embeddings endpoint working - generated {len(data.get('embeddings', []))} embeddings")
                    print(f"   Provider used: {data.get('provider_used')}")
                    print(f"   Processing time: {data.get('processing_time', 0):.2f}s")
                    return True
                else:
                    print(f"❌ AI embeddings failed: {data.get('error')}")
                    return False
            else:
                print(f"❌ AI embeddings endpoint returned {response.status_code}: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing AI embeddings: {e}")
        return False

async def test_vector_store_endpoint():
    """Test the new vector store endpoint"""
    try:
        payload = {
            "entity_data": {
                "key": "TEST-001",
                "summary": "Test issue for Phase 3-4 integration",
                "description": "This is a test issue to validate the ETL AI integration",
                "priority": "High",
                "assignee": "test-user"
            },
            "table_name": "work_items",
            "record_id": "TEST-001"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:3001/api/v1/ai/vectors/store",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print(f"✅ Vector store endpoint working")
                    print(f"   Point ID: {data.get('point_id')}")
                    print(f"   Collection: {data.get('collection_name')}")
                    print(f"   Provider used: {data.get('provider_used')}")
                    return True
                else:
                    print(f"❌ Vector store failed: {data.get('error')}")
                    return False
            else:
                print(f"❌ Vector store endpoint returned {response.status_code}: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing vector store: {e}")
        return False

async def test_vector_search_endpoint():
    """Test the new vector search endpoint"""
    try:
        payload = {
            "query_text": "test issue integration",
            "table_name": "work_items",
            "similarity_threshold": 0.5,
            "limit": 5
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:3001/api/v1/ai/vectors/search",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    print(f"✅ Vector search endpoint working")
                    print(f"   Found {data.get('total_found', 0)} results")
                    print(f"   Collections searched: {data.get('collections_searched', [])}")
                    print(f"   Provider used: {data.get('provider_used')}")
                    return True
                else:
                    print(f"❌ Vector search failed: {data.get('error')}")
                    return False
            else:
                print(f"❌ Vector search endpoint returned {response.status_code}: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing vector search: {e}")
        return False

async def test_etl_ai_client():
    """Test the ETL AI Client enhancements"""
    try:
        from app.clients.ai_client import get_ai_client
        
        client = get_ai_client()
        
        # Test connection
        connection_ok = await client.test_connection()
        if connection_ok:
            print("✅ ETL AI Client connection test passed")
        else:
            print("❌ ETL AI Client connection test failed")
            return False
        
        # Test vector storage method
        entity_data = {
            "key": "ETL-TEST-001",
            "summary": "ETL AI Client test issue",
            "description": "Testing the enhanced ETL AI Client",
            "priority": "Medium"
        }
        
        store_result = await client.store_entity_vector(
            entity_data=entity_data,
            table_name="work_items",
            record_id="ETL-TEST-001"
        )
        
        if store_result.success:
            print("✅ ETL AI Client vector storage test passed")
            print(f"   Point ID: {store_result.point_id}")
            print(f"   Collection: {store_result.collection_name}")
        else:
            print(f"❌ ETL AI Client vector storage test failed: {store_result.error}")
            return False
        
        # Test vector search method
        search_result = await client.search_similar_entities(
            query_text="ETL test issue",
            table_name="work_items",
            limit=3
        )
        
        if search_result.success:
            print("✅ ETL AI Client vector search test passed")
            print(f"   Found {search_result.total_found} results")
        else:
            print(f"❌ ETL AI Client vector search test failed: {search_result.error}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing ETL AI Client: {e}")
        return False

async def main():
    """Run all Phase 3-4 integration tests"""
    print("🚀 Starting Phase 3-4 ETL AI Integration Tests")
    print("=" * 60)
    
    # Test Backend Service health
    if not await test_backend_service_health():
        print("\n❌ Backend Service is not running. Please start it first.")
        return False
    
    print()
    
    # Test existing AI embeddings endpoint
    if not await test_ai_embeddings_endpoint():
        print("\n❌ AI embeddings endpoint test failed")
        return False
    
    print()
    
    # Test new vector store endpoint
    if not await test_vector_store_endpoint():
        print("\n❌ Vector store endpoint test failed")
        return False
    
    print()
    
    # Test new vector search endpoint
    if not await test_vector_search_endpoint():
        print("\n❌ Vector search endpoint test failed")
        return False
    
    print()
    
    # Test ETL AI Client enhancements
    if not await test_etl_ai_client():
        print("\n❌ ETL AI Client test failed")
        return False
    
    print()
    print("🎉 All Phase 3-4 integration tests passed!")
    print("✅ ETL → Backend → Qdrant integration is working correctly")
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
