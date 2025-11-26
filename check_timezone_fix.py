"""
Test script to verify timezone fix for next_run calculation
"""
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import sys
import os

# Add backend-service to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services', 'backend-service'))

# Import after path is set
from app.core.utils import DateTimeHelper

# Database connection
engine = create_engine('postgresql://postgres:pulse@localhost:5432/pulse_db')
conn = engine.connect()

print("\n" + "="*80)
print("🔍 TIMEZONE FIX VERIFICATION")
print("="*80)

# Get current times
now_naive = DateTimeHelper.now_default()
now_utc = datetime.utcnow()
now_local = datetime.now()

print(f"\n📅 Current Times:")
print(f"  - DateTimeHelper.now_default() (NY timezone-naive): {now_naive}")
print(f"  - datetime.utcnow() (UTC):                          {now_utc}")
print(f"  - datetime.now() (Local):                           {now_local}")

# Get jobs from database
rows = conn.execute(text("""
    SELECT id, job_name, next_run, schedule_interval_minutes, 
           last_run_started_at, status->>'overall' as overall_status
    FROM etl_jobs 
    ORDER BY id
""")).fetchall()

print(f"\n📊 Jobs in Database:")
print("-" * 80)

for row in rows:
    job_id, job_name, next_run, interval, last_run, status = row
    
    print(f"\n🔹 Job {job_id}: {job_name}")
    print(f"   Status: {status}")
    print(f"   Schedule Interval: {interval} minutes")
    print(f"   Last Run Started: {last_run}")
    print(f"   Next Run (DB): {next_run}")
    
    if next_run:
        # Calculate time difference
        diff = next_run - now_naive
        hours = diff.total_seconds() / 3600
        print(f"   Time Until Next Run: {hours:.2f} hours ({diff.total_seconds()/60:.0f} minutes)")
        
        # Check if it matches expected interval
        if last_run:
            expected_next = last_run + timedelta(minutes=interval)
            print(f"   Expected Next Run: {expected_next}")
            if abs((next_run - expected_next).total_seconds()) > 60:
                print(f"   ⚠️  WARNING: next_run doesn't match expected calculation!")

print("\n" + "="*80)
print("✅ Verification Complete")
print("="*80 + "\n")

conn.close()

