#!/usr/bin/env python3
"""
Test script for multi-tenant worker architecture.

This script demonstrates:
1. Creating tenant-specific queues
2. Starting/stopping tenant-specific workers
3. Publishing messages to tenant queues
4. Monitoring worker status

Usage:
    python scripts/test_multitenant_workers.py
"""

import sys
import os
import asyncio
import json
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.etl.queue.queue_manager import QueueManager
from app.workers.worker_manager import get_worker_manager
from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def test_multitenant_workers():
    """Test multi-tenant worker functionality."""
    
    print("🚀 Testing Multi-Tenant Worker Architecture")
    print("=" * 50)
    
    # Initialize components
    queue_manager = QueueManager()
    worker_manager = get_worker_manager()
    
    # Test tenant IDs
    test_tenants = [1, 2, 3]
    
    try:
        # 1. Setup tenant-specific queues
        print("\n📋 Step 1: Setting up tenant-specific queues")
        for tenant_id in test_tenants:
            queue_name = queue_manager.setup_tenant_queue(tenant_id, 'transform')
            print(f"  ✅ Created queue: {queue_name}")
        
        # 2. Start tenant-specific workers
        print("\n🔧 Step 2: Starting tenant-specific workers")
        for tenant_id in test_tenants:
            success = worker_manager.start_tenant_workers(tenant_id)
            status = "✅ Started" if success else "❌ Failed"
            print(f"  {status} workers for tenant {tenant_id}")
        
        # 3. Check worker status
        print("\n📊 Step 3: Checking worker status")
        overall_status = worker_manager.get_worker_status()
        print(f"  Overall running: {overall_status['running']}")
        print(f"  Total workers: {overall_status['worker_count']}")
        print(f"  Active tenants: {overall_status['tenant_count']}")
        
        for tenant_id in test_tenants:
            tenant_status = worker_manager.get_tenant_worker_status(tenant_id)
            print(f"  Tenant {tenant_id}: {tenant_status['worker_count']} workers")
        
        # 4. Publish test messages to tenant queues
        print("\n📤 Step 4: Publishing test messages")
        for tenant_id in test_tenants:
            success = queue_manager.publish_transform_job(
                tenant_id=tenant_id,
                integration_id=1,
                raw_data_id=999,  # Test ID
                data_type='test_message'
            )
            status = "✅ Published" if success else "❌ Failed"
            print(f"  {status} test message to tenant {tenant_id} queue")
        
        # 5. Wait a bit for processing
        print("\n⏳ Step 5: Waiting for message processing...")
        await asyncio.sleep(5)
        
        # 6. Test stopping specific tenant workers
        print("\n🛑 Step 6: Testing tenant worker control")
        test_tenant = test_tenants[0]
        print(f"  Stopping workers for tenant {test_tenant}")
        success = worker_manager.stop_tenant_workers(test_tenant)
        status = "✅ Stopped" if success else "❌ Failed"
        print(f"  {status} workers for tenant {test_tenant}")
        
        # Check status after stopping
        tenant_status = worker_manager.get_tenant_worker_status(test_tenant)
        print(f"  Tenant {test_tenant} has workers: {tenant_status['has_workers']}")
        
        # 7. Restart the tenant workers
        print(f"  Restarting workers for tenant {test_tenant}")
        success = worker_manager.start_tenant_workers(test_tenant)
        status = "✅ Restarted" if success else "❌ Failed"
        print(f"  {status} workers for tenant {test_tenant}")
        
        # 8. Final status check
        print("\n📈 Step 7: Final status check")
        final_status = worker_manager.get_worker_status()
        print(f"  Final worker count: {final_status['worker_count']}")
        print(f"  Final tenant count: {final_status['tenant_count']}")
        
        print("\n🎉 Multi-tenant worker test completed successfully!")
        
        # Display detailed status
        print("\n📋 Detailed Worker Status:")
        print(json.dumps(final_status, indent=2))
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"\n❌ Test failed: {e}")
        return False
    
    finally:
        # Cleanup: Stop all workers
        print("\n🧹 Cleanup: Stopping all workers")
        worker_manager.stop_all_workers()
        print("  ✅ All workers stopped")
    
    return True


def test_queue_naming():
    """Test queue naming conventions."""
    print("\n🏷️  Testing Queue Naming Conventions")
    print("-" * 40)
    
    queue_manager = QueueManager()
    
    test_cases = [
        (1, 'transform'),
        (2, 'transform'),
        (10, 'transform'),
        (1, 'vectorization'),
        (2, 'vectorization'),
    ]
    
    for tenant_id, queue_type in test_cases:
        queue_name = queue_manager.get_tenant_queue_name(tenant_id, queue_type)
        print(f"  Tenant {tenant_id}, {queue_type}: {queue_name}")


def main():
    """Main test function."""
    print("🧪 Multi-Tenant Worker Architecture Test Suite")
    print("=" * 60)
    
    # Test 1: Queue naming
    test_queue_naming()
    
    # Test 2: Full worker lifecycle
    try:
        result = asyncio.run(test_multitenant_workers())
        if result:
            print("\n✅ All tests passed!")
            return 0
        else:
            print("\n❌ Some tests failed!")
            return 1
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Test suite failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
