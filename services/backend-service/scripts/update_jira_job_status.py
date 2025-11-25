"""
Update existing Jira job in database to add 5th step (jira_sprint_reports).

This script updates the status JSON for the Jira ETL job to include the new
sprint reports step without requiring a full migration rollback/reapply.
"""

import sys
import os
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.database import get_database
from sqlalchemy import text

def update_jira_job_status():
    """Update Jira job status to include 5th step."""
    
    db = get_database()
    
    try:
        # Get write session
        with db.get_write_session() as session:
            # Get current Jira job
            result = session.execute(text("""
                SELECT id, status 
                FROM etl_jobs 
                WHERE job_name = 'Jira'
            """)).fetchone()
            
            if not result:
                print("❌ No Jira job found in database")
                return False
            
            job_id, current_status = result
            
            print(f"📋 Found Jira job (ID: {job_id})")
            print(f"Current steps: {list(current_status.get('steps', {}).keys())}")
            
            # Check if already has 5th step
            if 'jira_sprint_reports' in current_status.get('steps', {}):
                print("✅ Jira job already has jira_sprint_reports step")
                return True
            
            # Add the 5th step
            current_status['steps']['jira_sprint_reports'] = {
                'order': 5,
                'display_name': 'Sprint Reports',
                'extraction': 'idle',
                'transform': 'idle',
                'embedding': 'idle'
            }
            
            # Update the database
            session.execute(text("""
                UPDATE etl_jobs 
                SET status = :status 
                WHERE id = :job_id
            """), {
                'status': json.dumps(current_status),
                'job_id': job_id
            })
            
            session.commit()
            
            print(f"✅ Updated Jira job with 5th step: jira_sprint_reports")
            print(f"New steps: {list(current_status.get('steps', {}).keys())}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error updating Jira job: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = update_jira_job_status()
    sys.exit(0 if success else 1)

