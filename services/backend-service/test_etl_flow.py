#!/usr/bin/env python3
"""
Test script to trigger ETL extraction flow and monitor the debug logs.
"""

import sys
import os
import time
import logging

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_etl_extraction_flow():
    """Test the ETL extraction flow by publishing a message and monitoring."""
    try:
        logger.info("🚀 Testing ETL extraction flow...")
        
        # Import the QueueManager
        from app.etl.queue.queue_manager import QueueManager
        
        # Create queue manager instance
        queue_manager = QueueManager()
        logger.info(f"✅ QueueManager created: {queue_manager.host}:{queue_manager.port}/{queue_manager.vhost}")
        
        # Ensure queues exist
        logger.info("🔍 Setting up queues...")
        queue_manager.setup_queues()
        logger.info("✅ Queues setup completed")
        
        # Test message for jira_statuses_and_relationships extraction
        test_message = {
            'tenant_id': 1,
            'integration_id': 1,
            'job_id': 1,
            'extraction_type': 'jira_statuses_and_relationships'
        }
        
        # Publish to extraction queue
        logger.info("📤 Publishing test message for jira_statuses_and_relationships extraction...")
        success = queue_manager._publish_message('extraction_queue_premium', test_message)
        
        if success:
            logger.info("✅ Message published successfully")
            logger.info(f"📋 Message content: {test_message}")
        else:
            logger.error("❌ Message publishing failed")
            return False
            
        # Check queue status
        logger.info("🔍 Checking queue status...")
        try:
            with queue_manager.get_channel() as channel:
                method = channel.queue_declare(queue='extraction_queue_premium', passive=True)
                message_count = method.method.message_count
                logger.info(f"📊 extraction_queue_premium has {message_count} messages")
        except Exception as queue_error:
            logger.error(f"❌ Error checking queue: {queue_error}")
        
        logger.info("🎯 Message published! Now start the backend service to see if workers process it.")
        logger.info("💡 Look for debug logs with '🔍 [DEBUG]' in the backend service output.")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting ETL extraction flow test...")
    
    # Test ETL flow
    success = test_etl_extraction_flow()
    
    if success:
        logger.info("🎉 Test completed successfully!")
        logger.info("📝 Next steps:")
        logger.info("   1. Start the backend service: python -m uvicorn app.main:app --host 0.0.0.0 --port 3001")
        logger.info("   2. Watch for debug logs with '🔍 [DEBUG]' prefix")
        logger.info("   3. Check if the extraction worker processes the message")
    else:
        logger.error("❌ Test failed")
    
    logger.info("🏁 Test complete")
