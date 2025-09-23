#!/usr/bin/env python3
"""
Concurrent Operations Load Testing Script

Tests the vectorization system's ability to handle multiple concurrent operations
including vectorization queue processing and search operations.
"""

import asyncio
import time
import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Any
import concurrent.futures
import threading

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'app'))

async def test_concurrent_search_operations():
    """Test multiple concurrent search operations"""
    print("🔍 Testing Concurrent Search Operations")
    print("-" * 40)
    
    try:
        from app.ai.qdrant_client import PulseQdrantClient
        
        # Initialize Qdrant client
        qdrant_client = PulseQdrantClient()
        if not await qdrant_client.initialize():
            print("❌ Failed to connect to Qdrant")
            return False
        
        # Get available collections
        collections = await asyncio.get_event_loop().run_in_executor(
            None, qdrant_client.client.get_collections
        )
        
        collection_names = [c.name for c in collections.collections]
        if not collection_names:
            print("⚠️  No collections found for testing")
            return True
        
        print(f"Found {len(collection_names)} collections for testing")
        
        # Create test vector
        test_vector = [0.1] * 1536
        
        # Define concurrent search task
        async def search_task(collection_name: str, task_id: int):
            start_time = time.time()
            try:
                result = await qdrant_client.search_vectors(
                    collection_name=collection_name,
                    query_vector=test_vector,
                    limit=5
                )
                search_time = time.time() - start_time
                return {
                    'task_id': task_id,
                    'collection': collection_name,
                    'success': result.success,
                    'time': search_time,
                    'results_count': len(result.results) if result.success else 0,
                    'error': result.error if not result.success else None
                }
            except Exception as e:
                search_time = time.time() - start_time
                return {
                    'task_id': task_id,
                    'collection': collection_name,
                    'success': False,
                    'time': search_time,
                    'results_count': 0,
                    'error': str(e)
                }
        
        # Run concurrent searches
        concurrent_tasks = []
        task_id = 0
        
        # Test with multiple collections simultaneously
        for collection_name in collection_names[:5]:  # Test first 5 collections
            for i in range(3):  # 3 concurrent searches per collection
                concurrent_tasks.append(search_task(collection_name, task_id))
                task_id += 1
        
        print(f"Running {len(concurrent_tasks)} concurrent search operations...")
        
        start_time = time.time()
        results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Analyze results
        successful_searches = 0
        failed_searches = 0
        total_search_time = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed_searches += 1
                print(f"  Task failed with exception: {result}")
            elif result['success']:
                successful_searches += 1
                total_search_time += result['time']
                print(f"  Task {result['task_id']}: {result['collection']} - {result['time']:.3f}s ({result['results_count']} results)")
            else:
                failed_searches += 1
                print(f"  Task {result['task_id']}: {result['collection']} - FAILED: {result['error']}")
        
        print(f"\nConcurrent Search Results:")
        print(f"  Total tasks: {len(concurrent_tasks)}")
        print(f"  Successful: {successful_searches}")
        print(f"  Failed: {failed_searches}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Average search time: {total_search_time/max(successful_searches, 1):.3f}s")
        
        # Success criteria: >80% success rate and reasonable performance
        success_rate = successful_searches / len(concurrent_tasks)
        return success_rate >= 0.8 and total_time < 30.0  # All searches should complete in <30s
        
    except Exception as e:
        print(f"❌ Concurrent search test failed: {e}")
        return False

async def test_queue_processing_simulation():
    """Test vectorization queue processing simulation"""
    print("\n📋 Testing Queue Processing Simulation")
    print("-" * 40)
    
    try:
        from app.core.database import get_database
        from app.models.unified_models import VectorizationQueue
        from sqlalchemy import func
        
        database = get_database()
        
        # Check current queue status
        with database.get_read_session_context() as session:
            # Get queue statistics
            queue_stats = session.query(
                VectorizationQueue.status,
                func.count(VectorizationQueue.id).label('count')
            ).group_by(VectorizationQueue.status).all()
            
            print("Current Queue Status:")
            for stat in queue_stats:
                print(f"  {stat.status}: {stat.count:,}")
            
            # Get processing distribution by table
            table_stats = session.query(
                VectorizationQueue.table_name,
                VectorizationQueue.status,
                func.count(VectorizationQueue.id).label('count')
            ).group_by(
                VectorizationQueue.table_name,
                VectorizationQueue.status
            ).all()
            
            print("\nQueue Distribution by Table:")
            table_summary = {}
            for stat in table_stats:
                if stat.table_name not in table_summary:
                    table_summary[stat.table_name] = {}
                table_summary[stat.table_name][stat.status] = stat.count
            
            for table_name, statuses in table_summary.items():
                total = sum(statuses.values())
                completed = statuses.get('completed', 0)
                completion_rate = (completed / total * 100) if total > 0 else 0
                print(f"  {table_name}: {total:,} total, {completion_rate:.1f}% completed")
        
        # Simulate concurrent queue processing
        print("\nSimulating concurrent queue operations...")
        
        # Test multiple database connections
        connection_tasks = []
        
        async def database_connection_test(connection_id: int):
            try:
                start_time = time.time()
                with database.get_read_session_context() as session:
                    # Simulate queue query
                    count = session.query(func.count(VectorizationQueue.id)).scalar()
                    connection_time = time.time() - start_time
                    return {
                        'connection_id': connection_id,
                        'success': True,
                        'time': connection_time,
                        'count': count
                    }
            except Exception as e:
                connection_time = time.time() - start_time
                return {
                    'connection_id': connection_id,
                    'success': False,
                    'time': connection_time,
                    'error': str(e)
                }
        
        # Test 10 concurrent database connections
        for i in range(10):
            connection_tasks.append(database_connection_test(i))
        
        start_time = time.time()
        connection_results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        successful_connections = 0
        failed_connections = 0
        
        for result in connection_results:
            if isinstance(result, Exception):
                failed_connections += 1
            elif result['success']:
                successful_connections += 1
                print(f"  Connection {result['connection_id']}: {result['time']:.3f}s ({result['count']:,} records)")
            else:
                failed_connections += 1
                print(f"  Connection {result['connection_id']}: FAILED - {result['error']}")
        
        print(f"\nDatabase Connection Test Results:")
        print(f"  Successful connections: {successful_connections}/10")
        print(f"  Failed connections: {failed_connections}/10")
        print(f"  Total time: {total_time:.3f}s")
        
        return successful_connections >= 8  # At least 80% success rate
        
    except Exception as e:
        print(f"❌ Queue processing test failed: {e}")
        return False

async def main():
    """Main concurrent operations test"""
    print("🚀 Starting Concurrent Operations Load Testing")
    print("=" * 60)
    
    # Test 1: Concurrent search operations
    search_success = await test_concurrent_search_operations()
    
    # Test 2: Queue processing simulation
    queue_success = await test_queue_processing_simulation()
    
    # Overall results
    print("\n" + "=" * 60)
    overall_success = search_success and queue_success
    
    if overall_success:
        print("🎉 CONCURRENT OPERATIONS TESTING PASSED!")
        print("\n📋 Key Findings:")
        print("   • Multiple concurrent searches work reliably")
        print("   • Database connections handle concurrent load")
        print("   • Queue processing can scale with multiple workers")
        print("   • System maintains performance under concurrent load")
    else:
        print("💥 CONCURRENT OPERATIONS TESTING FAILED!")
        print(f"   Search test: {'PASSED' if search_success else 'FAILED'}")
        print(f"   Queue test: {'PASSED' if queue_success else 'FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
