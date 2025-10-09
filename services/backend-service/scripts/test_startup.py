#!/usr/bin/env python3
"""
Test script to verify backend service startup components.
"""

import os
import sys
import asyncio

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_startup_components():
    """Test each startup component individually."""
    
    print("🧪 Backend Service Startup Component Test")
    print("=" * 50)
    
    try:
        # Test 1: Basic imports
        print("\n1️⃣ Testing basic imports...")
        from app.core.database import get_database
        from app.core.config import get_settings
        print("✅ Core imports successful")
        
        # Test 2: Settings
        print("\n2️⃣ Testing settings...")
        settings = get_settings()
        print(f"✅ Settings loaded - DEBUG: {settings.DEBUG}, PORT: {settings.PORT}")
        
        # Test 3: Database connection
        print("\n3️⃣ Testing database connection...")
        database = get_database()
        with database.get_session_context() as session:
            from sqlalchemy import text
            result = session.execute(text("SELECT 1")).fetchone()
            print("✅ Database connection successful")
            
        # Test 4: Job scheduler imports
        print("\n4️⃣ Testing job scheduler imports...")
        from app.etl.job_scheduler import start_job_scheduler, get_job_timer_manager
        print("✅ Job scheduler imports successful")
        
        # Test 5: Test startup sequence (without actually starting)
        print("\n5️⃣ Testing startup sequence...")
        
        # Simulate the startup sequence from main.py
        print("🔍 Simulating startup sequence...")
        
        # Clear sessions (like in startup)
        print("🔍 Testing session clearing...")
        if not settings.DEBUG:
            print("   - Would clear sessions (production mode)")
        else:
            print("   - Session clearing disabled (development mode)")
            
        # Test job scheduler startup
        print("🔍 Testing job scheduler startup...")
        await asyncio.sleep(2)  # Simulate the 2-second delay
        
        print("🔍 Getting job timer manager...")
        manager = get_job_timer_manager()
        print("✅ Job timer manager obtained")
        
        # Test getting active jobs
        print("🔍 Testing active jobs query...")
        with database.get_session_context() as session:
            query = text("""
                SELECT id, job_name, tenant_id, active, status
                FROM etl_jobs
                WHERE active = TRUE
                ORDER BY id
            """)
            results = session.execute(query).fetchall()
            print(f"✅ Found {len(results)} active jobs")
            
            for row in results:
                print(f"   - Job: {row[1]} (ID: {row[0]}, Status: {row[4]}, Tenant: {row[2]})")
        
        print("\n✅ All startup component tests passed!")
        print("\n🚀 The backend service should start successfully.")
        print("If it's not working, the issue might be:")
        print("1. FastAPI startup event not being triggered")
        print("2. Exception being swallowed during startup")
        print("3. Async context issues")
        
    except Exception as e:
        print(f"\n❌ Error during startup test: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_startup_components())
