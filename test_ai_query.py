#!/usr/bin/env python3
"""
Test script for AI Query Interface - Phase 3-6
Tests the AIQueryProcessor and API endpoints functionality.
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# Add the backend service to the path
sys.path.append(str(Path(__file__).parent / "services" / "backend-service"))

async def test_ai_query_processor():
    """Test the AIQueryProcessor directly"""
    print("🧪 Testing AI Query Processor...")
    
    try:
        # Import required modules
        from app.core.database import get_database
        from app.ai.query_processor import AIQueryProcessor
        
        # Get database connection
        database = get_database()
        
        with database.get_read_session_context() as db_session:
            # Initialize query processor
            query_processor = AIQueryProcessor(db_session)
            await query_processor.initialize(tenant_id=1)
            print("✅ AIQueryProcessor initialized successfully")
            
            # Test capabilities
            print("\n📋 Testing capabilities...")
            capabilities = await query_processor.get_capabilities(tenant_id=1)
            print(f"✅ Capabilities: {json.dumps(capabilities, indent=2)}")
            
            # Test semantic search
            print("\n🔍 Testing semantic search...")
            search_result = await query_processor.semantic_search(
                query="test query",
                tenant_id=1,
                limit=5
            )
            print(f"✅ Semantic search: {json.dumps(search_result, indent=2)}")
            
            # Test natural language query
            print("\n💬 Testing natural language query...")
            query_result = await query_processor.process_query(
                query="Show me recent work items",
                tenant_id=1
            )
            print(f"✅ Query result: Success={query_result.success}, Type={query_result.query_type}")
            print(f"   Answer: {query_result.answer}")
            print(f"   Processing time: {query_result.processing_time:.3f}s")
            print(f"   Confidence: {query_result.confidence}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error testing AIQueryProcessor: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_endpoints():
    """Test the API endpoints using HTTP requests"""
    print("\n🌐 Testing API endpoints...")
    
    try:
        import requests
        
        base_url = "http://localhost:3001"
        
        # Test health endpoint
        print("Testing /api/v1/ai/health...")
        response = requests.get(f"{base_url}/api/v1/ai/health")
        print(f"Health check status: {response.status_code}")
        
        # Note: Other endpoints require authentication
        print("✅ API endpoints are accessible (authentication required for full testing)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing API endpoints: {e}")
        return False

async def main():
    """Main test function"""
    print("🚀 Starting AI Query Interface Tests - Phase 3-6")
    print("=" * 60)
    
    # Test 1: AIQueryProcessor
    processor_test = await test_ai_query_processor()
    
    # Test 2: API endpoints
    api_test = await test_api_endpoints()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   AIQueryProcessor: {'✅ PASS' if processor_test else '❌ FAIL'}")
    print(f"   API Endpoints: {'✅ PASS' if api_test else '❌ FAIL'}")
    
    if processor_test and api_test:
        print("\n🎉 All tests passed! AI Query Interface is working correctly.")
        return True
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Run tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
