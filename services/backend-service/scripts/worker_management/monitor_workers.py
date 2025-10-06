#!/usr/bin/env python3
"""
Worker monitoring utility script for Health Pulse ETL system.

This is a standalone utility script for monitoring worker status from command line.
For web-based monitoring, use the admin dashboard at /admin/workers.

Usage:
    python scripts/worker_management/monitor_workers.py           # One-time status check
    python scripts/worker_management/monitor_workers.py -c       # Continuous monitoring
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Add the app directory to Python path
app_dir = Path(__file__).parent.parent.parent / "app"
sys.path.insert(0, str(app_dir))

# Setup logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def get_queue_stats():
    """Get queue statistics from RabbitMQ."""
    try:
        from app.etl.queue.queue_manager import QueueManager
        queue_manager = QueueManager()
        
        # Note: This would require RabbitMQ management API
        # For now, we'll return basic info
        return {
            'transform_queue': {
                'messages': 'N/A (requires RabbitMQ management API)',
                'consumers': 'N/A'
            }
        }
    except Exception as e:
        return {'error': str(e)}


def get_worker_status():
    """Get current worker status."""
    try:
        from app.workers.worker_manager import get_worker_manager
        manager = get_worker_manager()
        return manager.get_worker_status()
    except Exception as e:
        return {'error': str(e)}


def get_raw_data_stats():
    """Get raw extraction data statistics."""
    try:
        from app.core.database import get_database
        from sqlalchemy import text
        
        database = get_database()
        with database.get_session_context() as session:
            # Get counts by status
            query = text("""
                SELECT 
                    status,
                    type,
                    COUNT(*) as count,
                    MIN(created_at) as oldest,
                    MAX(created_at) as newest
                FROM raw_extraction_data 
                WHERE active = true
                GROUP BY status, type
                ORDER BY status, type
            """)
            
            result = session.execute(query).fetchall()
            
            stats = {}
            for row in result:
                key = f"{row.status}_{row.type}"
                stats[key] = {
                    'count': row.count,
                    'oldest': row.oldest.isoformat() if row.oldest else None,
                    'newest': row.newest.isoformat() if row.newest else None
                }
            
            return stats
            
    except Exception as e:
        return {'error': str(e)}


def print_status_dashboard():
    """Print a comprehensive status dashboard."""
    print("\n" + "="*80)
    print(f"🔍 HEALTH PULSE WORKER MONITORING DASHBOARD")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Worker Status
    print("\n📊 WORKER STATUS:")
    worker_status = get_worker_status()
    if 'error' in worker_status:
        print(f"   ❌ Error: {worker_status['error']}")
    else:
        print(f"   🔄 Manager Running: {worker_status.get('running', False)}")
        for worker_name, status in worker_status.get('workers', {}).items():
            running = status.get('worker_running', False)
            thread_alive = status.get('thread_alive', False)
            thread_name = status.get('thread_name', 'N/A')
            
            status_icon = "🟢" if running and thread_alive else "🔴"
            print(f"   {status_icon} {worker_name}: Running={running}, Thread={thread_name}")
    
    # Queue Statistics
    print("\n📬 QUEUE STATISTICS:")
    queue_stats = get_queue_stats()
    if 'error' in queue_stats:
        print(f"   ❌ Error: {queue_stats['error']}")
    else:
        for queue_name, stats in queue_stats.items():
            print(f"   📦 {queue_name}: {stats}")
    
    # Raw Data Statistics
    print("\n📋 RAW DATA PROCESSING STATUS:")
    raw_stats = get_raw_data_stats()
    if 'error' in raw_stats:
        print(f"   ❌ Error: {raw_stats['error']}")
    else:
        if not raw_stats:
            print("   ✅ No raw data in queue")
        else:
            for key, stats in raw_stats.items():
                status, data_type = key.split('_', 1)
                icon = "⏳" if status == 'pending' else "✅" if status == 'completed' else "❌"
                print(f"   {icon} {status.upper()} {data_type}: {stats['count']} records")
                if stats['oldest']:
                    print(f"      📅 Oldest: {stats['oldest']}")
    
    print("\n" + "="*80)


def monitor_continuous():
    """Run continuous monitoring."""
    print("🚀 Starting continuous worker monitoring...")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            print_status_dashboard()
            time.sleep(10)  # Update every 10 seconds
            
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped by user")


def monitor_once():
    """Run monitoring once and exit."""
    print_status_dashboard()


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Health Pulse Worker Monitor')
    parser.add_argument('--continuous', '-c', action='store_true', 
                       help='Run continuous monitoring')
    
    args = parser.parse_args()
    
    if args.continuous:
        monitor_continuous()
    else:
        monitor_once()


if __name__ == "__main__":
    main()
