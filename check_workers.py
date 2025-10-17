#!/usr/bin/env python3
"""
Quick script to check worker status
"""
import sys
import os

# Add the backend service to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'backend-service'))

def check_workers():
    """Check the current status of workers."""
    try:
        from app.workers.worker_manager import get_worker_manager
        
        worker_manager = get_worker_manager()
        
        print("=== WORKER MANAGER STATUS ===")
        print(f"Running: {worker_manager.running}")
        print(f"Total workers: {len(worker_manager.workers)}")
        print(f"Total threads: {len(worker_manager.worker_threads)}")
        
        if worker_manager.workers:
            print("\n=== ACTIVE WORKERS ===")
            for worker_key, worker in worker_manager.workers.items():
                thread = worker_manager.worker_threads.get(worker_key)
                thread_status = "ALIVE" if thread and thread.is_alive() else "DEAD"
                print(f"{worker_key}: {thread_status}")
        else:
            print("\n❌ No workers found!")
            
        print("\n=== TIER WORKERS ===")
        for tier, tier_workers in worker_manager.tier_workers.items():
            print(f"{tier} tier:")
            for worker_type, workers in tier_workers.items():
                print(f"  {worker_type}: {len(workers)} workers")
                
        # Try to get worker status
        try:
            status = worker_manager.get_worker_status()
            print(f"\n=== WORKER STATUS ===")
            for key, value in status.items():
                print(f"{key}: {value}")
        except Exception as e:
            print(f"\n❌ Error getting worker status: {e}")

    except Exception as e:
        print(f"Error checking workers: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_workers()
