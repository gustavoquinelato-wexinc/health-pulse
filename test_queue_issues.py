#!/usr/bin/env python3
"""
Test script to manually queue issues extraction
"""
import sys
import os

# Add the backend service to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'backend-service'))

def test_queue_issues():
    """Test manually queuing issues extraction."""
    try:
        from app.etl.queue.queue_manager import QueueManager
        
        queue_manager = QueueManager()
        
        # Create the message that should be queued after statuses extraction
        message = {
            'tenant_id': 1,
            'integration_id': 1,  # Assuming integration ID 1
            'job_id': 1,          # Assuming job ID 1
            'type': 'jira_issues_with_changelogs'
        }
        
        # Get tenant tier and route to tier-based queue
        tier = queue_manager._get_tenant_tier(1)
        tier_queue = queue_manager.get_tier_queue_name(tier, 'extraction')
        
        print(f"=== MANUAL QUEUE TEST ===")
        print(f"Tenant 1 tier: {tier}")
        print(f"Target queue: {tier_queue}")
        print(f"Message: {message}")
        
        # Try to publish the message
        success = queue_manager._publish_message(tier_queue, message)
        
        if success:
            print(f"✅ Successfully queued issues extraction message")
            
            # Check queue stats after publishing
            stats = queue_manager.get_queue_stats(tier_queue)
            if stats:
                print(f"Queue stats after publish: {stats['message_count']} messages, {stats['consumer_count']} consumers")
            else:
                print("❌ Could not get queue stats")
                
        else:
            print(f"❌ Failed to queue issues extraction message")

    except Exception as e:
        print(f"Error testing queue: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_queue_issues()
