#!/usr/bin/env python3
"""
Script to set ETL jobs to run immediately for testing.
"""

import os
import sys
from datetime import datetime, timedelta

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def trigger_jobs_now():
    """Set active ETL jobs to run immediately."""
    
    print("⏰ Setting ETL Jobs to Run Now")
    print("=" * 40)
    
    try:
        from app.core.database import get_database
        from sqlalchemy import text
        
        database = get_database()
        
        with database.get_session_context() as session:
            # Get active jobs
            query = text("""
                SELECT id, job_name, next_run, schedule_interval_minutes
                FROM etl_jobs 
                WHERE active = TRUE
                ORDER BY id
            """)
            jobs = session.execute(query).fetchall()
            
            if not jobs:
                print("❌ No active jobs found")
                return
                
            print(f"Found {len(jobs)} active jobs:")
            
            # Set next_run to now + 1 minute for each job (staggered)
            now = datetime.now()
            
            for i, job in enumerate(jobs):
                # Stagger jobs by 2 minutes each
                trigger_time = now + timedelta(minutes=i * 2 + 1)
                
                current_next_run = job[2].strftime('%Y-%m-%d %H:%M:%S') if job[2] else 'None'
                new_next_run = trigger_time.strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"\n📋 Job: {job[1]} (ID: {job[0]})")
                print(f"   Current next_run: {current_next_run}")
                print(f"   New next_run: {new_next_run}")
                
                # Update the job
                update_query = text("""
                    UPDATE etl_jobs 
                    SET next_run = :next_run, last_updated_at = NOW()
                    WHERE id = :job_id
                """)
                session.execute(update_query, {
                    'next_run': trigger_time,
                    'job_id': job[0]
                })
                
            session.commit()
            print(f"\n✅ Updated {len(jobs)} jobs to run soon!")
            
            # Show the schedule
            print(f"\n📅 Execution Schedule:")
            for i, job in enumerate(jobs):
                trigger_time = now + timedelta(minutes=i * 2 + 1)
                print(f"   - {job[1]}: {trigger_time.strftime('%H:%M:%S')} (in {i * 2 + 1} minutes)")
                
            print(f"\n🚀 Jobs will start executing in 1 minute!")
            print("💡 Start your backend service now to see them run automatically")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    trigger_jobs_now()
