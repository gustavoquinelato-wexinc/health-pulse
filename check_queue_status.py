#!/usr/bin/env python3
"""
Quick script to check RabbitMQ queue status
"""
import sys
import os

# Add the backend service to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'backend-service'))

from app.etl.queue.queue_manager import QueueManager

def check_queue_status():
    """Check the current status of RabbitMQ queues."""
    try:
        queue_manager = QueueManager()
        
        # Check all tier-based queues
        tiers = ['free', 'basic', 'premium', 'enterprise']
        queue_types = ['extraction', 'transform', 'embedding']
        
        print("=== RABBITMQ QUEUE STATUS ===")
        print(f"{'QUEUE NAME':<30} {'MESSAGES':<10} {'CONSUMERS':<10}")
        print("-" * 55)
        
        for tier in tiers:
            for queue_type in queue_types:
                queue_name = queue_manager.get_tier_queue_name(tier, queue_type)
                stats = queue_manager.get_queue_stats(queue_name)
                
                if stats:
                    messages = stats['message_count']
                    consumers = stats['consumer_count']
                    print(f"{queue_name:<30} {messages:<10} {consumers:<10}")
                else:
                    print(f"{queue_name:<30} {'ERROR':<10} {'ERROR':<10}")
        
        # Check tenant tier for tenant 1
        print(f"\n=== TENANT 1 TIER ===")
        tier = queue_manager._get_tenant_tier(1)
        print(f"Tenant 1 tier: {tier}")
        
        # Show which queues tenant 1 would use
        print(f"\nTenant 1 would use these queues:")
        for queue_type in queue_types:
            queue_name = queue_manager.get_tier_queue_name(tier, queue_type)
            print(f"  {queue_type}: {queue_name}")

    except Exception as e:
        print(f"Error checking queue status: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_queue_status()
