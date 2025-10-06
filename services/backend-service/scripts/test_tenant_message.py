#!/usr/bin/env python3
"""
Quick test script to publish a message to a specific tenant's queue.

Usage:
    python scripts/test_tenant_message.py --tenant-id 1
"""

import sys
import argparse
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.etl.queue.queue_manager import QueueManager
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def test_tenant_message(tenant_id: int):
    """Test publishing a message to a specific tenant's queue."""
    
    print(f"📤 Testing message publishing to Tenant {tenant_id}")
    print("=" * 50)
    
    try:
        queue_manager = QueueManager()
        
        # Get tenant queue name
        queue_name = queue_manager.get_tenant_queue_name(tenant_id, 'transform')
        print(f"Target queue: {queue_name}")
        
        # Publish test message
        success = queue_manager.publish_transform_job(
            tenant_id=tenant_id,
            integration_id=1,
            raw_data_id=999,  # Test raw data ID
            data_type='test_tenant_message'
        )
        
        if success:
            print(f"✅ Successfully published test message to tenant {tenant_id} queue")
            print(f"   Queue: {queue_name}")
            print(f"   Message type: test_tenant_message")
            print(f"   Raw data ID: 999")
        else:
            print(f"❌ Failed to publish message to tenant {tenant_id} queue")
            
    except Exception as e:
        print(f"💥 Error: {e}")
        logger.error(f"Failed to test tenant message: {e}")


def main():
    parser = argparse.ArgumentParser(description='Test tenant-specific message publishing')
    parser.add_argument('--tenant-id', type=int, default=1, help='Tenant ID to test (default: 1)')
    
    args = parser.parse_args()
    
    test_tenant_message(args.tenant_id)


if __name__ == "__main__":
    main()
