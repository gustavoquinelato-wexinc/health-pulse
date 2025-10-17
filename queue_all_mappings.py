#!/usr/bin/env python3
"""
Simple script to queue all mapping tables for embedding.
Use this when you want to embed all mapping tables at once.
"""

import sys
sys.path.append('.')
from app.etl.queue.queue_manager import QueueManager

def queue_all_mapping_tables(tenant_id: int = 1):
    """Queue all 4 mapping tables for bulk embedding."""
    
    queue_manager = QueueManager()
    
    mapping_tables = [
        'status_mappings',
        'wits_mappings', 
        'wits_hierarchies',
        'workflows'
    ]
    
    print("🚀 Queuing all mapping tables for embedding...")
    print("=" * 50)
    
    success_count = 0
    for table_name in mapping_tables:
        success = queue_manager.publish_mapping_table_embedding(
            tenant_id=tenant_id,
            table_name=table_name
        )
        
        if success:
            print(f"✅ {table_name} queued successfully")
            success_count += 1
        else:
            print(f"❌ Failed to queue {table_name}")
    
    print("=" * 50)
    print(f"📊 Queued {success_count}/{len(mapping_tables)} mapping tables")
    
    if success_count == len(mapping_tables):
        print("🎉 All mapping tables queued! Check logs for processing progress.")
        print("💡 Processing will take 2-5 minutes with rate limiting.")
    else:
        print("⚠️ Some tables failed to queue. Check RabbitMQ connection.")

if __name__ == "__main__":
    queue_all_mapping_tables()
