#!/usr/bin/env python3
"""
Quick script to check ETL job status
"""
import sys
import os

# Add the backend service to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'backend-service'))

from app.core.database import get_database
from sqlalchemy import text

def check_job_status():
    """Check the current status of ETL jobs."""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Get ETL job status
            query = text("""
                SELECT 
                    id,
                    name,
                    status,
                    last_run_at,
                    last_success_at,
                    next_run,
                    active
                FROM etl_jobs
                WHERE tenant_id = 1
                ORDER BY id
            """)
            
            result = session.execute(query)
            jobs = result.fetchall()
            
            print("=== ETL JOBS STATUS ===")
            print(f"{'ID':<3} {'NAME':<15} {'STATUS':<10} {'LAST_RUN':<20} {'LAST_SUCCESS':<20} {'NEXT_RUN':<20} {'ACTIVE'}")
            print("-" * 110)
            
            for job in jobs:
                job_id = job[0]
                name = job[1]
                status = job[2]
                last_run = job[3].strftime('%Y-%m-%d %H:%M:%S') if job[3] else 'Never'
                last_success = job[4].strftime('%Y-%m-%d %H:%M:%S') if job[4] else 'Never'
                next_run = job[5].strftime('%Y-%m-%d %H:%M:%S') if job[5] else 'Not scheduled'
                active = job[6]
                
                print(f"{job_id:<3} {name:<15} {status:<10} {last_run:<20} {last_success:<20} {next_run:<20} {active}")

    except Exception as e:
        print(f"Error checking job status: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_job_status()
