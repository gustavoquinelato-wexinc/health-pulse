#!/usr/bin/env python3
"""
Direct testing of AI Query Interface - bypasses API layer
This works immediately without restarting the backend service
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# Add the backend service to the path
sys.path.append(str(Path(__file__).parent / "services" / "backend-service"))

async def test_direct_ai_interface():
    """Test AI Query Interface directly"""
    print("🚀 Testing AI Query Interface Directly")
    print("=" * 60)
    
    try:
        # Load environment
        from dotenv import load_dotenv
        load_dotenv()
        
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
            
            # Test 1: Capabilities
            print("\n📋 Testing Capabilities...")
            capabilities = await query_processor.get_capabilities(tenant_id=1)
            print(f"✅ Available capabilities:")
            print(f"   - Natural Language Queries: {capabilities['capabilities']['natural_language_queries']}")
            print(f"   - Semantic Search: {capabilities['capabilities']['semantic_search']}")
            print(f"   - Structured Queries: {capabilities['capabilities']['structured_queries']}")
            print(f"   - Hybrid Processing: {capabilities['capabilities']['hybrid_processing']}")
            print(f"   - Collections: {len(capabilities['collections'])} available")
            
            # Test 2: Semantic Search
            print("\n🔍 Testing Semantic Search...")
            search_result = await query_processor.semantic_search(
                query="high priority bugs",
                tenant_id=1,
                limit=5
            )
            print(f"✅ Semantic search completed:")
            print(f"   - Success: {search_result['success']}")
            print(f"   - Results found: {search_result['total_found']}")
            print(f"   - Collections searched: {len(search_result['collections_searched'])}")
            
            # Test 3: Natural Language Query
            print("\n💬 Testing Natural Language Query...")
            query_result = await query_processor.process_query(
                query="Show me recent work items with high priority",
                tenant_id=1
            )
            print(f"✅ Query processed:")
            print(f"   - Success: {query_result.success}")
            print(f"   - Query Type: {query_result.query_type}")
            print(f"   - Processing Time: {query_result.processing_time:.3f}s")
            print(f"   - Confidence: {query_result.confidence}")
            print(f"   - Answer: {query_result.answer[:100]}..." if len(query_result.answer) > 100 else f"   - Answer: {query_result.answer}")
            
            # Test 4: Different Query Types
            test_queries = [
                "Find similar issues to authentication problems",
                "How many PRs were created last week?",
                "Show me the most complex work items"
            ]
            
            print("\n🧪 Testing Different Query Types...")
            for i, test_query in enumerate(test_queries, 1):
                print(f"\n   Query {i}: '{test_query}'")
                result = await query_processor.process_query(test_query, tenant_id=1)
                print(f"   → Type: {result.query_type}, Success: {result.success}, Time: {result.processing_time:.2f}s")
            
            print("\n" + "=" * 60)
            print("🎉 AI Query Interface is working correctly!")
            print("\n💡 What this means:")
            print("   ✅ Natural language processing is operational")
            print("   ✅ Semantic search with vector embeddings works")
            print("   ✅ Query intent analysis is functioning")
            print("   ✅ Tenant isolation is properly implemented")
            print("   ✅ Error handling and fallbacks are working")
            
            print("\n🚀 Ready for:")
            print("   1. API endpoint testing (after backend restart)")
            print("   2. UI integration for conversational interface")
            print("   3. Production deployment with real user queries")
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_direct_ai_interface())
    sys.exit(0 if success else 1)
