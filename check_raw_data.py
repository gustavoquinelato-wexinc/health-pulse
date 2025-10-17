#!/usr/bin/env python3
"""
Quick script to check raw_extraction_data table status
"""
import sys
import os

# Add the backend service to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'services', 'backend-service'))

from app.core.database import get_database
from sqlalchemy import text

def check_raw_data_status():
    """Check the current status of raw_extraction_data table."""
    try:
        database = get_database()
        with database.get_read_session_context() as session:
            # Get recent records for tenant 1
            query = text("""
                SELECT 
                    id, 
                    type, 
                    status, 
                    created_at,
                    last_updated_at,
                    CASE 
                        WHEN error_details IS NOT NULL THEN 'HAS_ERROR'
                        ELSE 'NO_ERROR'
                    END as error_status,
                    CASE 
                        WHEN raw_data IS NOT NULL THEN 
                            CASE 
                                WHEN raw_data ? 'issues' THEN jsonb_array_length(raw_data->'issues')
                                WHEN raw_data ? 'projects' THEN jsonb_array_length(raw_data->'projects')
                                WHEN raw_data ? 'statuses' THEN jsonb_array_length(raw_data->'statuses')
                                ELSE 0
                            END
                        ELSE 0
                    END as data_count
                FROM raw_extraction_data
                WHERE tenant_id = 1
                ORDER BY created_at DESC
                LIMIT 20
            """)
            
            result = session.execute(query)
            records = result.fetchall()
            
            print("=== RAW EXTRACTION DATA STATUS ===")
            print(f"{'ID':<5} {'TYPE':<25} {'STATUS':<12} {'COUNT':<6} {'ERROR':<10} {'CREATED':<20}")
            print("-" * 85)
            
            for record in records:
                raw_id = record[0]
                data_type = record[1]
                status = record[2]
                created_at = record[3].strftime('%Y-%m-%d %H:%M:%S') if record[3] else 'N/A'
                error_status = record[5]
                data_count = record[6]
                
                print(f"{raw_id:<5} {data_type:<25} {status:<12} {data_count:<6} {error_status:<10} {created_at:<20}")
            
            # Get status summary
            print("\n=== STATUS SUMMARY ===")
            status_query = text("""
                SELECT status, COUNT(*) as count
                FROM raw_extraction_data
                WHERE tenant_id = 1
                GROUP BY status
                ORDER BY status
            """)
            status_result = session.execute(status_query)
            status_counts = status_result.fetchall()
            
            for row in status_counts:
                status = row[0]
                count = row[1]
                print(f"{status}: {count}")
                
            # Get type summary
            print("\n=== TYPE SUMMARY ===")
            type_query = text("""
                SELECT type, COUNT(*) as count
                FROM raw_extraction_data
                WHERE tenant_id = 1
                GROUP BY type
                ORDER BY type
            """)
            type_result = session.execute(type_query)
            type_counts = type_result.fetchall()
            
            for row in type_counts:
                data_type = row[0]
                count = row[1]
                print(f"{data_type}: {count}")

    except Exception as e:
        print(f"Error checking raw data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_raw_data_status()
