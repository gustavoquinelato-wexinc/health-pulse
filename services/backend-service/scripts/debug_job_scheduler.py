#!/usr/bin/env python3
"""
Debug script for ETL job scheduler functionality.
This script helps diagnose issues with the job auto-start functionality.
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def debug_job_scheduler():
    """Debug the job scheduler functionality step by step."""
    
    print("🔍 ETL Job Scheduler Debug Script")
    print("=" * 50)
    
    try:
        # Step 1: Test database connection
        print("\n1️⃣ Testing database connection...")
        from app.core.database import get_database
        database = get_database()
        
        with database.get_session_context() as session:
            from sqlalchemy import text
            result = session.execute(text("SELECT 1")).fetchone()
            print("✅ Database connection successful")
            
        # Step 2: Check active ETL jobs
        print("\n2️⃣ Checking active ETL jobs...")
        with database.get_session_context() as session:
            query = text("""
                SELECT id, job_name, active, status, next_run, tenant_id, 
                       schedule_interval_minutes, last_run_started_at
                FROM etl_jobs 
                WHERE active = TRUE 
                ORDER BY id
            """)
            results = session.execute(query).fetchall()
            
            print(f"Found {len(results)} active jobs:")
            for row in results:
                next_run_str = row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else 'None'
                last_run_str = row[7].strftime('%Y-%m-%d %H:%M:%S') if row[7] else 'None'
                print(f"  - ID: {row[0]}, Name: {row[1]}, Status: {row[3]}")
                print(f"    Next Run: {next_run_str}, Last Run: {last_run_str}")
                print(f"    Interval: {row[6]} minutes, Tenant: {row[5]}")
                
        # Step 3: Test job timer creation
        print("\n3️⃣ Testing individual job timer creation...")
        if results:
            job_id, job_name, active, status, next_run, tenant_id, interval, last_run = results[0]
            
            # Reset any RUNNING jobs to READY for testing
            if status == 'RUNNING':
                print(f"⚠️ Job '{job_name}' is RUNNING - resetting to READY for testing")
                with database.get_session_context() as session:
                    update_query = text("""
                        UPDATE etl_jobs 
                        SET status = 'READY', last_updated_at = NOW()
                        WHERE id = :job_id AND tenant_id = :tenant_id
                    """)
                    session.execute(update_query, {'job_id': job_id, 'tenant_id': tenant_id})
                    session.commit()
                    print(f"✅ Job '{job_name}' reset to READY")
            
            # Test creating individual timer
            from app.etl.job_scheduler import IndividualJobTimer
            timer = IndividualJobTimer(job_id, job_name, tenant_id)
            print(f"✅ Created timer for job '{job_name}' (ID: {job_id})")
            
            # Test calculating initial delay
            delay = await timer._calculate_initial_delay()
            if delay is not None:
                print(f"✅ Initial delay calculated: {delay:.1f} minutes")
            else:
                print("❌ Could not calculate initial delay")
                
        # Step 4: Test job timer manager
        print("\n4️⃣ Testing job timer manager...")
        from app.etl.job_scheduler import JobTimerManager
        manager = JobTimerManager()
        print("✅ Job timer manager created")
        
        # Step 5: Test starting all timers (but don't actually start them)
        print("\n5️⃣ Testing timer startup process...")
        print("🔍 Getting database connection for job scheduler...")
        with database.get_session_context() as session:
            print("🔍 Querying for active jobs...")
            query = text("""
                SELECT id, job_name, tenant_id
                FROM etl_jobs
                WHERE active = TRUE
                ORDER BY id
            """)
            results = session.execute(query).fetchall()
            print(f"🚀 Found {len(results)} active jobs for timer startup")
            
            for row in results:
                job_id, job_name, tenant_id = row
                print(f"🔍 Would start timer for job '{job_name}' (ID: {job_id}, tenant: {tenant_id})")
                
        print("\n✅ All diagnostic tests completed successfully!")
        print("\n📋 Next Steps:")
        print("1. If all tests passed, the issue might be in the FastAPI startup sequence")
        print("2. Check if the startup_event in main.py is being called")
        print("3. Look for any exceptions during server startup")
        
    except Exception as e:
        print(f"\n❌ Error during diagnostic: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(debug_job_scheduler())
