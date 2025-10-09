#!/usr/bin/env python3
"""
Quick fix script for common ETL job scheduling issues.
"""

import os
import sys
from datetime import datetime, timedelta

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def fix_etl_jobs():
    """Fix common ETL job issues."""
    
    print("🔧 ETL Jobs Quick Fix Script")
    print("=" * 40)
    
    try:
        from app.core.database import get_database
        from sqlalchemy import text
        
        database = get_database()
        
        with database.get_session_context() as session:
            # Issue 1: Reset RUNNING jobs to READY
            print("\n1️⃣ Fixing RUNNING jobs...")
            running_query = text("SELECT id, job_name FROM etl_jobs WHERE status = 'RUNNING'")
            running_jobs = session.execute(running_query).fetchall()
            
            if running_jobs:
                print(f"Found {len(running_jobs)} RUNNING jobs - resetting to READY:")
                for job in running_jobs:
                    print(f"  - Resetting {job[1]} (ID: {job[0]})")
                    
                reset_query = text("""
                    UPDATE etl_jobs 
                    SET status = 'READY', last_updated_at = NOW()
                    WHERE status = 'RUNNING'
                """)
                session.execute(reset_query)
                session.commit()
                print("✅ RUNNING jobs reset to READY")
            else:
                print("✅ No RUNNING jobs found")
                
            # Issue 2: Fix missing next_run times
            print("\n2️⃣ Fixing missing next_run times...")
            missing_next_run_query = text("""
                SELECT id, job_name, schedule_interval_minutes 
                FROM etl_jobs 
                WHERE active = TRUE AND next_run IS NULL
            """)
            missing_jobs = session.execute(missing_next_run_query).fetchall()
            
            if missing_jobs:
                print(f"Found {len(missing_jobs)} jobs with missing next_run - fixing:")
                for job in missing_jobs:
                    # Calculate next_run as now + interval
                    next_run = datetime.now() + timedelta(minutes=job[2])
                    print(f"  - Setting {job[1]} next_run to {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    fix_query = text("""
                        UPDATE etl_jobs 
                        SET next_run = :next_run, last_updated_at = NOW()
                        WHERE id = :job_id
                    """)
                    session.execute(fix_query, {'next_run': next_run, 'job_id': job[0]})
                    
                session.commit()
                print("✅ Missing next_run times fixed")
            else:
                print("✅ All active jobs have next_run times")
                
            # Issue 3: Show current job status
            print("\n3️⃣ Current job status:")
            status_query = text("""
                SELECT id, job_name, active, status, next_run, schedule_interval_minutes
                FROM etl_jobs 
                ORDER BY active DESC, id
            """)
            all_jobs = session.execute(status_query).fetchall()
            
            active_count = 0
            for job in all_jobs:
                status_icon = "🟢" if job[2] else "🔴"  # active
                next_run_str = job[4].strftime('%Y-%m-%d %H:%M:%S') if job[4] else 'None'
                print(f"  {status_icon} {job[1]} (ID: {job[0]}) - Status: {job[3]}, Next: {next_run_str}")
                if job[2]:  # active
                    active_count += 1
                    
            print(f"\n📊 Summary: {active_count} active jobs, {len(all_jobs) - active_count} inactive jobs")
            
            # Issue 4: Check for jobs ready to run now
            print("\n4️⃣ Checking for jobs ready to run now...")
            now = datetime.now()
            ready_query = text("""
                SELECT id, job_name, next_run
                FROM etl_jobs 
                WHERE active = TRUE 
                AND status = 'READY'
                AND next_run <= :now
            """)
            ready_jobs = session.execute(ready_query, {'now': now}).fetchall()
            
            if ready_jobs:
                print(f"⚠️ Found {len(ready_jobs)} jobs that should run now:")
                for job in ready_jobs:
                    next_run_str = job[2].strftime('%Y-%m-%d %H:%M:%S') if job[2] else 'None'
                    print(f"  - {job[1]} (scheduled for {next_run_str})")
                print("💡 These jobs should be triggered by the job scheduler")
            else:
                print("✅ No jobs are overdue")
                
        print("\n✅ ETL jobs fix completed!")
        print("\n📋 Next steps:")
        print("1. Start the backend service")
        print("2. Check logs for job scheduler startup messages")
        print("3. Active jobs should auto-execute at their next_run times")
        
    except Exception as e:
        print(f"\n❌ Error during fix: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    fix_etl_jobs()
