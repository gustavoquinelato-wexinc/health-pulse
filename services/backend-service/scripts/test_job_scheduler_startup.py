#!/usr/bin/env python3
"""
Test script to manually run the job scheduler startup sequence.
This helps identify where the startup is failing.
"""

import os
import sys
import asyncio

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_job_scheduler_startup():
    """Test the job scheduler startup sequence manually."""
    
    print("🧪 Job Scheduler Startup Test")
    print("=" * 50)
    
    try:
        # Step 1: Reset any RUNNING jobs to READY
        print("\n1️⃣ Resetting any RUNNING jobs to READY...")
        from app.core.database import get_database
        from sqlalchemy import text
        
        database = get_database()
        with database.get_session_context() as session:
            # Check for RUNNING jobs
            query = text("SELECT id, job_name, status FROM etl_jobs WHERE status = 'RUNNING'")
            running_jobs = session.execute(query).fetchall()
            
            if running_jobs:
                print(f"Found {len(running_jobs)} RUNNING jobs - resetting to READY:")
                for job in running_jobs:
                    print(f"  - Resetting job '{job[1]}' (ID: {job[0]}) from RUNNING to READY")
                
                # Reset them to READY
                update_query = text("""
                    UPDATE etl_jobs 
                    SET status = 'READY', last_updated_at = NOW()
                    WHERE status = 'RUNNING'
                """)
                session.execute(update_query)
                session.commit()
                print("✅ All RUNNING jobs reset to READY")
            else:
                print("✅ No RUNNING jobs found")
        
        # Step 2: Test the actual startup sequence
        print("\n2️⃣ Testing job scheduler startup sequence...")
        
        # Import and run the startup function
        from app.etl.job_scheduler import start_job_scheduler
        
        print("🚀 Calling start_job_scheduler()...")
        await start_job_scheduler()
        print("✅ Job scheduler startup completed successfully!")
        
        # Step 3: Check what timers were created
        print("\n3️⃣ Checking created timers...")
        from app.etl.job_scheduler import get_job_timer_manager
        
        manager = get_job_timer_manager()
        print(f"✅ Job timer manager has {len(manager.job_timers)} active timers:")
        
        for job_id, timer in manager.job_timers.items():
            print(f"  - Job ID: {job_id}, Name: {timer.job_name}, Running: {timer.running}")
            
        # Step 4: Check active jobs and their next run times
        print("\n4️⃣ Checking active jobs and next run times...")
        with database.get_session_context() as session:
            query = text("""
                SELECT id, job_name, status, next_run, schedule_interval_minutes
                FROM etl_jobs 
                WHERE active = TRUE 
                ORDER BY id
            """)
            results = session.execute(query).fetchall()
            
            print(f"Active jobs ({len(results)}):")
            for row in results:
                next_run_str = row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else 'None'
                print(f"  - {row[1]} (ID: {row[0]}): Status={row[2]}, Next Run={next_run_str}, Interval={row[4]}min")
                
        print("\n✅ Job scheduler test completed successfully!")
        print("\n📋 Summary:")
        print(f"- {len(manager.job_timers)} job timers created")
        print(f"- {len(results)} active jobs found")
        print("- All timers should now be running and scheduling jobs automatically")
        
        # Step 5: Wait a bit to see if any jobs trigger
        print("\n5️⃣ Waiting 30 seconds to see if any jobs trigger...")
        await asyncio.sleep(30)
        
        # Check if any jobs changed status
        with database.get_session_context() as session:
            query = text("""
                SELECT id, job_name, status, last_updated_at
                FROM etl_jobs 
                WHERE active = TRUE 
                ORDER BY last_updated_at DESC
            """)
            results = session.execute(query).fetchall()
            
            print("Job status after 30 seconds:")
            for row in results:
                updated_str = row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else 'None'
                print(f"  - {row[1]}: Status={row[2]}, Last Updated={updated_str}")
        
    except Exception as e:
        print(f"\n❌ Error during job scheduler test: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_job_scheduler_startup())
