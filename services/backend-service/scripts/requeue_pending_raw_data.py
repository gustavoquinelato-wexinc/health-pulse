"""
Script to requeue pending raw_extraction_data records to transform queue.

This script finds all pending records in raw_extraction_data table and
republishes them to the transform queue for processing.

Usage:
    python scripts/requeue_pending_raw_data.py [--tenant-id TENANT_ID] [--limit LIMIT]
"""

import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import get_database
from app.etl.queue.queue_manager import QueueManager
from sqlalchemy import text


def requeue_pending_records(tenant_id: int = None, limit: int = None):
    """
    Requeue pending raw_extraction_data records to transform queue.
    
    Args:
        tenant_id: Optional tenant ID to filter by
        limit: Optional limit on number of records to requeue
    """
    database = get_database()
    queue_manager = QueueManager()
    
    with database.get_read_session_context() as session:
        # Build query
        query = """
            SELECT id, tenant_id, integration_id, type, status, created_at
            FROM raw_extraction_data
            WHERE status = 'pending'
        """
        
        params = {}
        
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params['tenant_id'] = tenant_id
        
        query += " ORDER BY created_at ASC"
        
        if limit:
            query += " LIMIT :limit"
            params['limit'] = limit
        
        # Execute query
        result = session.execute(text(query), params)
        pending_records = result.fetchall()
        
        if not pending_records:
            print("✅ No pending records found")
            return
        
        print(f"Found {len(pending_records)} pending records")
        print("-" * 80)
        
        # Requeue each record
        success_count = 0
        failed_count = 0
        
        for record in pending_records:
            raw_data_id = record[0]
            rec_tenant_id = record[1]
            rec_integration_id = record[2]
            data_type = record[3]
            status = record[4]
            created_at = record[5]
            
            print(f"Requeuing: ID={raw_data_id}, Type={data_type}, Created={created_at}")
            
            try:
                # Publish to transform queue
                success = queue_manager.publish_transform_job(
                    tenant_id=rec_tenant_id,
                    integration_id=rec_integration_id,
                    raw_data_id=raw_data_id,
                    data_type=data_type
                )
                
                if success:
                    success_count += 1
                    print(f"  ✅ Queued successfully")
                else:
                    failed_count += 1
                    print(f"  ❌ Failed to queue")
                    
            except Exception as e:
                failed_count += 1
                print(f"  ❌ Error: {e}")
        
        print("-" * 80)
        print(f"✅ Successfully queued: {success_count}")
        print(f"❌ Failed to queue: {failed_count}")
        print(f"📊 Total processed: {len(pending_records)}")


def main():
    parser = argparse.ArgumentParser(description='Requeue pending raw_extraction_data records')
    parser.add_argument('--tenant-id', type=int, help='Filter by tenant ID')
    parser.add_argument('--limit', type=int, help='Limit number of records to requeue')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("REQUEUE PENDING RAW EXTRACTION DATA")
    print("=" * 80)
    print()
    
    if args.tenant_id:
        print(f"Tenant ID: {args.tenant_id}")
    else:
        print("Tenant ID: ALL")
    
    if args.limit:
        print(f"Limit: {args.limit}")
    else:
        print("Limit: NONE")
    
    print()
    
    requeue_pending_records(tenant_id=args.tenant_id, limit=args.limit)


if __name__ == '__main__':
    main()

