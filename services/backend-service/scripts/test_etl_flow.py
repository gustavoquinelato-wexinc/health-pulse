#!/usr/bin/env python3
"""
Test script for complete ETL flow: extract -> queue -> transform -> load.

This is a one-off utility script to test the ETL pipeline end-to-end.
"""

import os
import sys
import time
import json
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def create_test_raw_data():
    """Create test raw data for custom fields processing."""
    try:
        from app.core.database import get_database
        from sqlalchemy import text
        
        # Sample Jira createmeta response
        test_createmeta = {
            "projects": [
                {
                    "id": "10001",
                    "key": "TEST",
                    "name": "Test Project",
                    "projectTypeKey": "software",
                    "issuetypes": [
                        {
                            "id": "10001",
                            "name": "Story",
                            "description": "User story",
                            "hierarchyLevel": 0,
                            "fields": {
                                "customfield_10001": {
                                    "name": "Story Points",
                                    "schema": {"type": "number"}
                                },
                                "customfield_10002": {
                                    "name": "Epic Link",
                                    "schema": {"type": "string"}
                                }
                            }
                        },
                        {
                            "id": "10002",
                            "name": "Bug",
                            "description": "Software bug",
                            "hierarchyLevel": 0,
                            "fields": {
                                "customfield_10003": {
                                    "name": "Severity",
                                    "schema": {"type": "option"}
                                }
                            }
                        }
                    ]
                }
            ]
        }
        
        database = get_database()
        with database.get_session_context() as session:
            # Insert test raw data
            insert_query = text("""
                INSERT INTO raw_extraction_data (
                    type, raw_data, status, tenant_id, integration_id, created_at, last_updated_at, active
                ) VALUES (
                    :type, CAST(:raw_data AS jsonb), 'pending', :tenant_id, :integration_id, NOW(), NOW(), TRUE
                ) RETURNING id
            """)
            
            result = session.execute(insert_query, {
                'type': 'jira_custom_fields',
                'raw_data': json.dumps(test_createmeta),
                'tenant_id': 4,  # WEX tenant
                'integration_id': 28  # Jira integration
            })
            
            raw_data_id = result.fetchone()[0]
            session.commit()
            
            logger.info(f"✅ Created test raw data with ID: {raw_data_id}")
            return raw_data_id
            
    except Exception as e:
        logger.error(f"❌ Error creating test raw data: {e}")
        return None


def publish_test_message(raw_data_id):
    """Publish test message to transform queue."""
    try:
        from app.etl.queue.queue_manager import QueueManager
        
        queue_manager = QueueManager()
        
        success = queue_manager.publish_transform_job(
            tenant_id=4,
            integration_id=28,
            raw_data_id=raw_data_id,
            data_type='jira_custom_fields'
        )
        
        if success:
            logger.info(f"✅ Published message for raw_data_id: {raw_data_id}")
            return True
        else:
            logger.error("❌ Failed to publish message")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error publishing message: {e}")
        return False


def check_processing_results(raw_data_id):
    """Check if the data was processed successfully."""
    try:
        from app.core.database import get_database
        from sqlalchemy import text
        
        database = get_database()
        with database.get_session_context() as session:
            # Check raw data status
            status_query = text("""
                SELECT status, updated_at 
                FROM raw_extraction_data 
                WHERE id = :raw_data_id
            """)
            
            result = session.execute(status_query, {'raw_data_id': raw_data_id}).fetchone()
            
            if result:
                status, updated_at = result
                logger.info(f"📊 Raw data status: {status} (updated: {updated_at})")
                
                if status == 'completed':
                    # Check if projects were created
                    projects_query = text("""
                        SELECT COUNT(*) as count 
                        FROM projects 
                        WHERE tenant_id = 4 AND integration_id = 28 AND active = true
                    """)
                    
                    projects_count = session.execute(projects_query).fetchone()[0]
                    logger.info(f"📊 Projects created: {projects_count}")
                    
                    # Check if WITs were created
                    wits_query = text("""
                        SELECT COUNT(*) as count 
                        FROM wits 
                        WHERE tenant_id = 4 AND integration_id = 28 AND active = true
                    """)
                    
                    wits_count = session.execute(wits_query).fetchone()[0]
                    logger.info(f"📊 WITs created: {wits_count}")
                    
                    # Check if custom fields were created
                    cf_query = text("""
                        SELECT COUNT(*) as count 
                        FROM custom_fields 
                        WHERE tenant_id = 4 AND integration_id = 28 AND active = true
                    """)
                    
                    cf_count = session.execute(cf_query).fetchone()[0]
                    logger.info(f"📊 Custom fields created: {cf_count}")
                    
                    return status == 'completed'
                else:
                    return False
            else:
                logger.error("❌ Raw data not found")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error checking results: {e}")
        return False


def main():
    """Test the complete flow."""
    logger.info("🧪 Testing complete ETL flow...")
    
    # Step 1: Create test raw data
    logger.info("1️⃣ Creating test raw data...")
    raw_data_id = create_test_raw_data()
    if not raw_data_id:
        logger.error("❌ Failed to create test data")
        return False
    
    # Step 2: Publish message to queue
    logger.info("2️⃣ Publishing message to transform queue...")
    if not publish_test_message(raw_data_id):
        logger.error("❌ Failed to publish message")
        return False
    
    # Step 3: Wait for processing
    logger.info("3️⃣ Waiting for worker to process message...")
    logger.info("💡 Make sure workers are running: python -m uvicorn app.main:app --reload")
    
    max_wait = 30  # Wait up to 30 seconds
    wait_interval = 2  # Check every 2 seconds
    
    for i in range(max_wait // wait_interval):
        time.sleep(wait_interval)
        logger.info(f"⏳ Checking processing status... ({(i+1)*wait_interval}s)")
        
        if check_processing_results(raw_data_id):
            logger.info("✅ Processing completed successfully!")
            return True
    
    logger.warning("⚠️ Processing did not complete within timeout")
    logger.info("💡 Check worker logs or run: python scripts/worker_management/monitor_workers.py")
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
