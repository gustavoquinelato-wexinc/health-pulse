#!/usr/bin/env python3
"""
Manual job scheduler starter.
Run this after the backend service is running to start the job scheduler.
"""

import os
import sys
import asyncio
import time

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def start_job_scheduler_manual():
    """Start the job scheduler manually."""
    
    print("🚀 Manual Job Scheduler Startup")
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
            
        # Step 2: Check for active jobs
        print("\n2️⃣ Checking for active ETL jobs...")
        with database.get_session_context() as session:
            query = text("""
                SELECT id, job_name, active, status, next_run
                FROM etl_jobs 
                WHERE active = TRUE 
                ORDER BY id
            """)
            results = session.execute(query).fetchall()
            
            if not results:
                print("❌ No active ETL jobs found")
                return
                
            print(f"✅ Found {len(results)} active jobs:")
            for row in results:
                next_run_str = row[4].strftime('%Y-%m-%d %H:%M:%S') if row[4] else 'None'
                print(f"   - {row[1]} (ID: {row[0]}) - Status: {row[3]}, Next: {next_run_str}")
                
        # Step 3: Start the job scheduler
        print("\n3️⃣ Starting job scheduler...")
        from app.etl.job_scheduler import start_job_scheduler, get_job_timer_manager
        
        await start_job_scheduler()
        print("✅ Job scheduler started successfully!")
        
        # Step 4: Verify timers are running
        print("\n4️⃣ Verifying job timers...")
        manager = get_job_timer_manager()
        print(f"✅ {len(manager.job_timers)} job timers are now running:")
        
        for job_id, timer in manager.job_timers.items():
            print(f"   - Job '{timer.job_name}' (ID: {job_id}) - Running: {timer.running}")
            
        # Step 5: Show next execution times
        print("\n5️⃣ Next execution schedule:")
        with database.get_session_context() as session:
            query = text("""
                SELECT job_name, next_run, schedule_interval_minutes
                FROM etl_jobs 
                WHERE active = TRUE 
                ORDER BY next_run
            """)
            results = session.execute(query).fetchall()
            
            for row in results:
                if row[1]:
                    next_run_str = row[1].strftime('%Y-%m-%d %H:%M:%S')
                    print(f"   - {row[0]}: {next_run_str} (every {row[2]} minutes)")
                    
        print("\n✅ Job scheduler is now running!")
        print("🔄 Jobs will execute automatically at their scheduled times")
        print("📊 You can monitor job execution in the backend service logs")
        
        # Step 6: Keep the scheduler running
        print("\n6️⃣ Keeping scheduler running...")
        print("⏰ Press Ctrl+C to stop the job scheduler")
        
        try:
            while True:
                await asyncio.sleep(60)  # Check every minute
                
                # Show status every 5 minutes
                current_time = time.time()
                if not hasattr(start_job_scheduler_manual, 'last_status_time'):
                    start_job_scheduler_manual.last_status_time = current_time
                    
                if current_time - start_job_scheduler_manual.last_status_time >= 300:  # 5 minutes
                    print(f"\n⏰ Status check at {time.strftime('%H:%M:%S')}")
                    print(f"   - {len(manager.job_timers)} job timers still running")
                    start_job_scheduler_manual.last_status_time = current_time
                    
        except KeyboardInterrupt:
            print("\n🛑 Stopping job scheduler...")
            from app.etl.job_scheduler import stop_job_scheduler
            await stop_job_scheduler()
            print("✅ Job scheduler stopped")
            
    except Exception as e:
        print(f"\n❌ Error starting job scheduler: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(start_job_scheduler_manual())
