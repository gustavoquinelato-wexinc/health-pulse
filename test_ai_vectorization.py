#!/usr/bin/env python3
"""
Test script to verify AI vectorization with system token
"""

import sys
import os
import asyncio
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'etl-service'))

from app.jobs.orchestrator import _get_system_token
from app.clients.ai_client import bulk_store_entity_vectors_for_etl

async def test_ai_vectorization():
    """Test AI vectorization with system token"""
    print("Testing AI vectorization with system token...")
    
    # Get system token for tenant 1 (WEX)
    token = _get_system_token(1)
    
    if not token:
        print("❌ Failed to get system token")
        return False
    
    print(f"✅ Got system token: {token[:50]}...")
    
    # Test bulk vector storage
    test_entities = [
        {
            "entity_data": {
                "title": "Test Issue 1",
                "description": "This is a test issue for AI vectorization",
                "status": "Open"
            },
            "record_id": "test-1",
            "table_name": "issues"
        },
        {
            "entity_data": {
                "title": "Test Issue 2", 
                "description": "Another test issue for AI vectorization",
                "status": "In Progress"
            },
            "record_id": "test-2",
            "table_name": "issues"
        }
    ]
    
    try:
        result = await bulk_store_entity_vectors_for_etl(test_entities, auth_token=token)
        
        if result.success:
            print(f"✅ AI vectorization successful: {result.vectors_stored} vectors stored")
            print(f"   Provider: {result.provider_used}")
            print(f"   Processing time: {result.processing_time:.2f}s")
            return True
        else:
            print(f"❌ AI vectorization failed: {result.error}")
            return False
            
    except Exception as e:
        print(f"❌ Exception during AI vectorization: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_ai_vectorization())
    sys.exit(0 if success else 1)
