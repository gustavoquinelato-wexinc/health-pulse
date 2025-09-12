#!/usr/bin/env python3
"""
Simple script to check vectors stored in Qdrant after running ETL jobs
"""

import asyncio
import httpx
import json

async def check_qdrant_collections():
    """Check what collections exist in Qdrant"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:6333/collections")
            if response.status_code == 200:
                collections = response.json()
                print("🗂️  Qdrant Collections Found:")
                for collection in collections.get("result", {}).get("collections", []):
                    name = collection.get("name")
                    print(f"   📁 {name}")
                return collections
            else:
                print(f"❌ Failed to get collections: {response.status_code}")
                return None
    except Exception as e:
        print(f"❌ Error connecting to Qdrant: {e}")
        return None

async def check_collection_details(collection_name):
    """Get details about a specific collection"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:6333/collections/{collection_name}")
            if response.status_code == 200:
                details = response.json()
                result = details.get("result", {})
                print(f"\n📊 Collection: {collection_name}")
                print(f"   📈 Points Count: {result.get('points_count', 0)}")
                print(f"   📏 Vector Size: {result.get('config', {}).get('params', {}).get('vectors', {}).get('size', 'Unknown')}")
                print(f"   🏷️  Distance: {result.get('config', {}).get('params', {}).get('vectors', {}).get('distance', 'Unknown')}")
                return result
            else:
                print(f"❌ Failed to get collection details: {response.status_code}")
                return None
    except Exception as e:
        print(f"❌ Error getting collection details: {e}")
        return None

async def sample_vectors_from_collection(collection_name, limit=3):
    """Get sample vectors from a collection"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "limit": limit,
                "with_payload": True,
                "with_vector": False  # Don't need the actual vector data
            }
            response = await client.post(
                f"http://localhost:6333/collections/{collection_name}/points/scroll",
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                points = data.get("result", {}).get("points", [])
                print(f"\n🔍 Sample Vectors from {collection_name}:")
                for i, point in enumerate(points[:limit], 1):
                    payload_data = point.get("payload", {})
                    print(f"   {i}. ID: {point.get('id')}")
                    print(f"      📝 Summary: {payload_data.get('summary', 'N/A')[:100]}...")
                    print(f"      🏷️  Key: {payload_data.get('key', 'N/A')}")
                    print(f"      📅 Table: {payload_data.get('table_name', 'N/A')}")
                    print(f"      🏢 Tenant: {payload_data.get('tenant_id', 'N/A')}")
                    print()
                return points
            else:
                print(f"❌ Failed to get sample vectors: {response.status_code}")
                return None
    except Exception as e:
        print(f"❌ Error getting sample vectors: {e}")
        return None

async def test_semantic_search(collection_name, query_text="bug fix"):
    """Test semantic search via Backend Service"""
    try:
        # Note: This requires authentication token
        print(f"\n🔍 Testing Semantic Search for: '{query_text}'")
        print("   ⚠️  Note: This requires authentication token")
        
        payload = {
            "query_text": query_text,
            "table_name": collection_name.split("_")[-1],  # Extract table name
            "limit": 3
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:3001/api/v1/ai/vectors/search",
                json=payload,
                headers={"Authorization": "Bearer YOUR_TOKEN_HERE"}  # Replace with real token
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    results = data.get("results", [])
                    print(f"   ✅ Found {len(results)} similar items:")
                    for i, result in enumerate(results, 1):
                        print(f"      {i}. Score: {result.get('score', 0):.3f}")
                        print(f"         Key: {result.get('payload', {}).get('key', 'N/A')}")
                        print(f"         Summary: {result.get('payload', {}).get('summary', 'N/A')[:80]}...")
                else:
                    print(f"   ❌ Search failed: {data.get('error')}")
            else:
                print(f"   ❌ Search request failed: {response.status_code}")
                if response.status_code == 401:
                    print("   💡 Tip: You need a valid authentication token")
                
    except Exception as e:
        print(f"❌ Error testing semantic search: {e}")

async def main():
    """Main function to check Qdrant vectors"""
    print("🚀 Checking Qdrant Vectors After ETL Jobs")
    print("=" * 50)
    
    # 1. Check what collections exist
    collections_data = await check_qdrant_collections()
    if not collections_data:
        print("\n❌ Cannot connect to Qdrant. Make sure it's running on localhost:6333")
        return
    
    collections = collections_data.get("result", {}).get("collections", [])
    if not collections:
        print("\n📭 No collections found. Run some ETL jobs first!")
        return
    
    # 2. Check details for each collection
    for collection in collections:
        collection_name = collection.get("name")
        if collection_name and "client_" in collection_name:
            await check_collection_details(collection_name)
            await sample_vectors_from_collection(collection_name)
    
    # 3. Test semantic search (if collections exist)
    work_items_collections = [c.get("name") for c in collections if "work_items" in c.get("name", "")]
    if work_items_collections:
        await test_semantic_search(work_items_collections[0])
    
    print("\n🎉 Qdrant vector check complete!")
    print("\n💡 Tips:")
    print("   - Run ETL jobs to generate more vectors")
    print("   - Use Qdrant dashboard: http://localhost:6333/dashboard")
    print("   - Test semantic search via Backend Service API")

if __name__ == "__main__":
    asyncio.run(main())
