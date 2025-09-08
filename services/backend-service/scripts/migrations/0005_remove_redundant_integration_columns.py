#!/usr/bin/env python3
"""
Migration 0005: Remove redundant integration columns
- Remove performance_config column (not used)
- Remove configuration column (not used)

These columns were identified as redundant since we have specific
JSON columns for all needed configuration:
- model_config: AI model parameters
- provider_metadata: Provider-specific settings  
- cost_config: Cost tracking and limits
- fallback_integration_id: Fallback integration reference
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from app.core.config import AppConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    """Remove redundant integration columns"""
    try:
        # Load configuration
        config = AppConfig()
        
        # Connect to database
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            logger.info("Starting migration 0005: Remove redundant integration columns")
            
            # Check if columns exist before dropping
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'integrations' 
                AND column_name IN ('performance_config', 'configuration')
            """)
            existing_columns = [row['column_name'] for row in cursor.fetchall()]
            
            if 'performance_config' in existing_columns:
                logger.info("Dropping performance_config column...")
                cursor.execute("ALTER TABLE integrations DROP COLUMN performance_config")
                logger.info("✅ Dropped performance_config column")
            else:
                logger.info("⚠️ performance_config column does not exist, skipping")
            
            if 'configuration' in existing_columns:
                logger.info("Dropping configuration column...")
                cursor.execute("ALTER TABLE integrations DROP COLUMN configuration")
                logger.info("✅ Dropped configuration column")
            else:
                logger.info("⚠️ configuration column does not exist, skipping")
            
            # Verify remaining columns
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'integrations' 
                AND column_name LIKE '%config%'
                ORDER BY column_name
            """)
            remaining_config_columns = [row['column_name'] for row in cursor.fetchall()]
            logger.info(f"Remaining config columns: {remaining_config_columns}")
            
            # Expected columns: ['cost_config', 'model_config']
            expected_columns = ['cost_config', 'model_config']
            if set(remaining_config_columns) == set(expected_columns):
                logger.info("✅ Integration table now has only the required JSON columns")
            else:
                logger.warning(f"⚠️ Unexpected columns found: {remaining_config_columns}")
            
            logger.info("✅ Migration 0005 completed successfully")
            
    except Exception as e:
        logger.error(f"❌ Migration 0005 failed: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

def rollback_migration():
    """Rollback migration by adding the columns back"""
    try:
        # Load configuration
        config = AppConfig()
        
        # Connect to database
        conn = psycopg2.connect(config.DATABASE_URL)
        conn.autocommit = True
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            logger.info("Rolling back migration 0005: Adding redundant integration columns back")
            
            # Add performance_config column back
            cursor.execute("""
                ALTER TABLE integrations 
                ADD COLUMN IF NOT EXISTS performance_config JSONB DEFAULT '{}'
            """)
            logger.info("✅ Added performance_config column back")
            
            # Add configuration column back
            cursor.execute("""
                ALTER TABLE integrations 
                ADD COLUMN IF NOT EXISTS configuration JSONB DEFAULT '{}'
            """)
            logger.info("✅ Added configuration column back")
            
            logger.info("✅ Migration 0005 rollback completed successfully")
            
    except Exception as e:
        logger.error(f"❌ Migration 0005 rollback failed: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rollback_migration()
    else:
        run_migration()
