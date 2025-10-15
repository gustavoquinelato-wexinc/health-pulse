"""
Diagnostic script to check why transform queue is not processing.

This script checks:
1. Worker status (running/stopped)
2. Queue message counts
3. Pending raw_extraction_data records
4. Recent worker errors

Usage:
    python scripts/diagnose_queue_processing.py [--tenant-id TENANT_ID]
"""

import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import get_database
from app.etl.queue.queue_manager import QueueManager
from app.workers.worker_manager import get_worker_manager
from sqlalchemy import text


def diagnose_queue_processing(tenant_id: int = 1):
    """
    Diagnose why transform queue is not processing.
    
    Args:
        tenant_id: Tenant ID to check
    """
    print("=" * 80)
    print("QUEUE PROCESSING DIAGNOSTIC")
    print("=" * 80)
    print(f"Tenant ID: {tenant_id}")
    print(f"Timestamp: {datetime.now()}")
    print()
    
    # 1. Check Worker Status
    print("-" * 80)
    print("1. WORKER STATUS")
    print("-" * 80)
    
    try:
        manager = get_worker_manager()
        status = manager.get_tenant_worker_status(tenant_id)
        
        print(f"Has Workers: {status.get('has_workers', False)}")
        print(f"Tenant ID: {status.get('tenant_id', 'N/A')}")
        print()
        
        if status.get('has_workers'):
            workers = status.get('workers', {})
            
            # Transform workers
            if 'transform' in workers:
                transform = workers['transform']
                print(f"Transform Workers: {transform.get('count', 0)}")
                for instance in transform.get('instances', []):
                    worker_num = instance.get('worker_number', 0)
                    running = instance.get('worker_running', False)
                    alive = instance.get('thread_alive', False)
                    status_str = "✅ RUNNING" if (running and alive) else "❌ STOPPED"
                    print(f"  Worker {worker_num + 1}: {status_str}")
                print()
            else:
                print("❌ No transform workers found")
                print()
            
            # Vectorization workers
            if 'vectorization' in workers:
                vectorization = workers['vectorization']
                print(f"Vectorization Workers: {vectorization.get('count', 0)}")
                for instance in vectorization.get('instances', []):
                    worker_num = instance.get('worker_number', 0)
                    running = instance.get('worker_running', False)
                    alive = instance.get('thread_alive', False)
                    status_str = "✅ RUNNING" if (running and alive) else "❌ STOPPED"
                    print(f"  Worker {worker_num + 1}: {status_str}")
                print()
            else:
                print("❌ No vectorization workers found")
                print()
        else:
            print("❌ NO WORKERS RUNNING FOR THIS TENANT")
            print()
            print("💡 Solution: Go to Queue Management page and click 'Start Workers'")
            print()
            
    except Exception as e:
        print(f"❌ Error checking worker status: {e}")
        print()
    
    # 2. Check Queue Stats
    print("-" * 80)
    print("2. QUEUE STATISTICS")
    print("-" * 80)
    
    try:
        queue_manager = QueueManager()
        
        # Transform queue
        transform_queue = queue_manager.get_tenant_queue_name(tenant_id, 'transform')
        transform_stats = queue_manager.get_queue_stats(transform_queue)
        
        if transform_stats:
            print(f"Transform Queue: {transform_queue}")
            print(f"  Messages: {transform_stats.get('message_count', 0)}")
            print(f"  Consumers: {transform_stats.get('consumer_count', 0)}")
            
            if transform_stats.get('message_count', 0) > 0 and transform_stats.get('consumer_count', 0) == 0:
                print(f"  ⚠️  WARNING: Messages in queue but no consumers!")
                print(f"  💡 Solution: Start workers to consume messages")
            print()
        else:
            print(f"❌ Could not get stats for {transform_queue}")
            print()
        
        # Vectorization queue
        vectorization_queue = queue_manager.get_tenant_queue_name(tenant_id, 'vectorization')
        vectorization_stats = queue_manager.get_queue_stats(vectorization_queue)
        
        if vectorization_stats:
            print(f"Vectorization Queue: {vectorization_queue}")
            print(f"  Messages: {vectorization_stats.get('message_count', 0)}")
            print(f"  Consumers: {vectorization_stats.get('consumer_count', 0)}")
            print()
        else:
            print(f"❌ Could not get stats for {vectorization_queue}")
            print()
            
    except Exception as e:
        print(f"❌ Error checking queue stats: {e}")
        print()
    
    # 3. Check Pending Raw Data
    print("-" * 80)
    print("3. PENDING RAW EXTRACTION DATA")
    print("-" * 80)
    
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Count by status
            status_query = text("""
                SELECT status, COUNT(*) as count
                FROM raw_extraction_data
                WHERE tenant_id = :tenant_id
                GROUP BY status
                ORDER BY status
            """)
            status_result = session.execute(status_query, {'tenant_id': tenant_id})
            status_counts = status_result.fetchall()
            
            print("Status Breakdown:")
            for row in status_counts:
                status = row[0]
                count = row[1]
                print(f"  {status}: {count}")
            print()
            
            # Get pending records
            pending_query = text("""
                SELECT id, type, created_at, error_details
                FROM raw_extraction_data
                WHERE tenant_id = :tenant_id AND status = 'pending'
                ORDER BY created_at ASC
                LIMIT 10
            """)
            pending_result = session.execute(pending_query, {'tenant_id': tenant_id})
            pending_records = pending_result.fetchall()
            
            if pending_records:
                print(f"First 10 Pending Records:")
                for record in pending_records:
                    raw_id = record[0]
                    data_type = record[1]
                    created_at = record[2]
                    error = record[3]
                    
                    age = datetime.now() - created_at.replace(tzinfo=None)
                    age_str = f"{age.total_seconds() / 60:.1f} minutes ago"
                    
                    print(f"  ID {raw_id}: {data_type} (created {age_str})")
                    if error:
                        print(f"    Error: {error}")
                print()
                
                print("💡 Solution: Run requeue script to republish these to the queue:")
                print(f"   python scripts/requeue_pending_raw_data.py --tenant-id {tenant_id}")
                print()
            else:
                print("✅ No pending records found")
                print()
                
    except Exception as e:
        print(f"❌ Error checking raw data: {e}")
        print()
    
    # 4. Check Recent Errors
    print("-" * 80)
    print("4. RECENT PROCESSING ERRORS")
    print("-" * 80)
    
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            error_query = text("""
                SELECT id, type, status, error_details, last_updated_at
                FROM raw_extraction_data
                WHERE tenant_id = :tenant_id
                AND error_details IS NOT NULL
                ORDER BY last_updated_at DESC
                LIMIT 5
            """)
            error_result = session.execute(error_query, {'tenant_id': tenant_id})
            error_records = error_result.fetchall()
            
            if error_records:
                print("Recent Errors:")
                for record in error_records:
                    raw_id = record[0]
                    data_type = record[1]
                    status = record[2]
                    error = record[3]
                    updated_at = record[4]
                    
                    print(f"  ID {raw_id}: {data_type} ({status})")
                    print(f"    Error: {error}")
                    print(f"    Time: {updated_at}")
                    print()
            else:
                print("✅ No recent errors found")
                print()
                
    except Exception as e:
        print(f"❌ Error checking errors: {e}")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("Next Steps:")
    print("1. If workers are STOPPED → Start workers via Queue Management page")
    print("2. If messages in queue but no consumers → Start workers")
    print("3. If pending records exist → Run requeue script")
    print("4. If errors exist → Check backend service logs for details")
    print()


def main():
    parser = argparse.ArgumentParser(description='Diagnose queue processing issues')
    parser.add_argument('--tenant-id', type=int, default=1, help='Tenant ID to check (default: 1)')
    
    args = parser.parse_args()
    
    diagnose_queue_processing(tenant_id=args.tenant_id)


if __name__ == '__main__':
    main()

