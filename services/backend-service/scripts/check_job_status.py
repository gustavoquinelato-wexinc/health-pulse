#!/usr/bin/env python3
"""
Check ETL job status and see which jobs are due to run
"""

from app.core.database import get_database
from sqlalchemy import text
from datetime import datetime
import pytz

def main():
    # Get current time in New York timezone (timezone-naive, same as database)
    ny_tz = pytz.timezone('America/New_York')
    now_aware = datetime.now(ny_tz)
    now = now_aware.replace(tzinfo=None)  # Make timezone-naive for comparison
    print(f'Current time (NY): {now.strftime("%Y-%m-%d %H:%M:%S")}')
    print()

    database = get_database()
    with database.get_session_context() as session:
        result = session.execute(text('SELECT id, job_name, status, next_run FROM etl_jobs WHERE active = true ORDER BY next_run')).fetchall()
        print('Active ETL Jobs:')
        for row in result:
            job_id, job_name, status, next_run = row
            if next_run:
                # Database stores times as timezone-naive in America/New_York timezone
                # (same as DateTimeHelper.now_default() behavior)
                if next_run.tzinfo is None:
                    # Database time is already in NY timezone, just compare directly
                    next_run_ny = next_run
                else:
                    # If somehow it has timezone info, convert to NY timezone
                    next_run_ny = next_run.astimezone(ny_tz).replace(tzinfo=None)

                is_due = next_run_ny <= now

                if is_due:
                    due_text = '(DUE NOW!)'
                else:
                    minutes_until = (next_run_ny - now).total_seconds() / 60
                    due_text = f'(in {minutes_until:.1f} minutes)'

                print(f'  - {job_name} (ID: {job_id}): {status}')
                print(f'    Next Run: {next_run_ny.strftime("%Y-%m-%d %H:%M:%S")} NY {due_text}')
            else:
                print(f'  - {job_name} (ID: {job_id}): {status} (No next run scheduled)')
            print()

if __name__ == "__main__":
    main()
