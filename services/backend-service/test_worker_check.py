"""
Test script to verify worker status check functionality.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.etl.workers.worker_manager import get_worker_manager


def test_worker_status_check():
    """Test the worker status check."""
    print("=" * 60)
    print("Testing Worker Status Check")
    print("=" * 60)
    
    manager = get_worker_manager()
    status = manager.get_worker_status()
    
    print(f"\n📊 Worker Manager Status:")
    print(f"   Running: {status.get('running', False)}")
    print(f"   Workers: {len(status.get('workers', {}))}")
    
    workers_running = status.get('running', False)
    
    if workers_running:
        print(f"\n✅ Workers are RUNNING")
        print(f"\n   Worker Details:")
        for worker_key, worker_info in status.get('workers', {}).items():
            print(f"   - {worker_key}:")
            print(f"     Count: {worker_info.get('count', 0)}")
            print(f"     Tier: {worker_info.get('tier', 'unknown')}")
            print(f"     Type: {worker_info.get('type', 'unknown')}")
    else:
        print(f"\n❌ Workers are STOPPED")
        print(f"\n   Message: No workers are currently running.")
        print(f"   Action: Please start workers from the Queue Management page.")
    
    print("\n" + "=" * 60)
    return workers_running


if __name__ == "__main__":
    result = test_worker_status_check()
    sys.exit(0 if result else 1)

