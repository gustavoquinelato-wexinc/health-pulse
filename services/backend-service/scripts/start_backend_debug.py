#!/usr/bin/env python3
"""
Debug version of backend service startup with detailed logging.
"""

import os
import sys
import asyncio
import uvicorn
from contextlib import asynccontextmanager

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@asynccontextmanager
async def debug_lifespan(app):
    """Debug version of the lifespan with detailed logging."""
    
    print("🚀 DEBUG: Starting Backend Service...")
    print("=" * 60)
    
    try:
        # Step 1: Test database
        print("\n1️⃣ Testing database connection...")
        from app.core.database import get_database
        database = get_database()
        
        with database.get_session_context() as session:
            from sqlalchemy import text
            result = session.execute(text("SELECT 1")).fetchone()
            print("✅ Database connection successful")
            
        # Step 2: Check settings
        print("\n2️⃣ Checking settings...")
        from app.core.config import get_settings
        settings = get_settings()
        print(f"✅ Settings loaded - DEBUG: {settings.DEBUG}, PORT: {settings.PORT}")
        
        # Step 3: Clear sessions
        print("\n3️⃣ Handling user sessions...")
        if not settings.DEBUG:
            print("   - Would clear sessions (production mode)")
        else:
            print("   - Session clearing disabled (development mode)")
            
        # Step 4: Start job scheduler with detailed logging
        print("\n4️⃣ Starting job scheduler...")
        await asyncio.sleep(2)  # 2 second delay like in main.py
        
        print("🚀 Attempting to start job scheduler...")
        try:
            from app.etl.job_scheduler import start_job_scheduler
            print("🔍 Job scheduler module imported successfully")
            
            # Call the startup function
            await start_job_scheduler()
            print("✅ Independent job scheduler started successfully")
            
            # Check what was created
            from app.etl.job_scheduler import get_job_timer_manager
            manager = get_job_timer_manager()
            print(f"✅ Job timer manager has {len(manager.job_timers)} active timers")
            
            # Show active jobs
            with database.get_session_context() as session:
                query = text("""
                    SELECT id, job_name, status, next_run, schedule_interval_minutes
                    FROM etl_jobs 
                    WHERE active = TRUE 
                    ORDER BY id
                """)
                results = session.execute(query).fetchall()
                
                print(f"📋 Active jobs ({len(results)}):")
                for row in results:
                    next_run_str = row[3].strftime('%Y-%m-%d %H:%M:%S') if row[3] else 'None'
                    print(f"   - {row[1]} (ID: {row[0]}): Next run at {next_run_str}")
                    
        except Exception as e:
            print(f"❌ CRITICAL: Error starting job scheduler: {e}")
            print(f"❌ Job scheduler error type: {type(e).__name__}")
            print(f"❌ Job scheduler error details: {str(e)}")
            import traceback
            print(f"❌ Job scheduler traceback: {traceback.format_exc()}")
            print("⚠️ Job scheduler not started - jobs will need manual triggering")
            
        print("\n✅ Backend Service startup completed")
        print("🌐 Service will be available at http://localhost:3001")
        print("📊 Job scheduler status messages should appear above")
        print("⏰ Jobs should auto-execute based on their next_run times")
        
        yield
        
    except Exception as e:
        print(f"❌ Failed to start Backend Service: {e}")
        import traceback
        print(f"❌ Startup traceback: {traceback.format_exc()}")
        yield

def start_debug_server():
    """Start the backend service with debug logging."""
    
    print("🔧 Starting Backend Service with Debug Logging")
    print("=" * 60)
    
    # Import FastAPI app
    from app.main import app
    
    # Replace the lifespan with our debug version
    app.router.lifespan_context = debug_lifespan
    
    # Start the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3001,
        log_level="info",
        reload=False  # Disable reload for cleaner output
    )

if __name__ == "__main__":
    start_debug_server()
