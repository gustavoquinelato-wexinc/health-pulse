#!/usr/bin/env python3
"""
Cleanup script to remove duplicate tenant names before adding UNIQUE constraint.
This script will:
1. Find all duplicate tenant names
2. Keep the oldest tenant for each name (lowest ID)
3. Merge or delete data from duplicate tenants
4. Remove the duplicate tenant records
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_database_connection():
    """Get database connection using environment variables"""
    try:
        connection = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DATABASE", "pulse_db"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "pulse")
        )
        return connection
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        sys.exit(1)

def find_duplicate_tenants(cursor):
    """Find all tenant names that have duplicates"""
    cursor.execute("""
        SELECT name, COUNT(*) as count, array_agg(id ORDER BY id) as tenant_ids
        FROM tenants 
        GROUP BY name 
        HAVING COUNT(*) > 1
        ORDER BY name;
    """)
    return cursor.fetchall()

def cleanup_tenant_data(cursor, tenant_id_to_remove, tenant_id_to_keep):
    """
    Clean up data for a tenant that will be removed.
    This is a safe cleanup that just deletes the data rather than trying to merge.
    """
    print(f"   🧹 Cleaning up data for tenant ID {tenant_id_to_remove}")
    
    # Delete in reverse dependency order
    tables_to_clean = [
        "etl_jobs",
        "users_permissions", 
        "users_sessions",
        "users",
        "system_settings",
        "prs_reviews",
        "prs_commits", 
        "prs_comments",
        "changelogs",
        "wits_prs_links",
        "prs",
        "work_items",
        "repositories",
        "projects",
        "wits",
        "statuses",
        "wits_mappings",
        "wits_hierarchies", 
        "statuses_mappings",
        "workflows",
        "integrations",
        "tenants_colors"
    ]
    
    for table in tables_to_clean:
        try:
            cursor.execute(f"DELETE FROM {table} WHERE tenant_id = %s;", (tenant_id_to_remove,))
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                print(f"     ✅ Deleted {deleted_count} rows from {table}")
        except Exception as e:
            print(f"     ⚠️ Error cleaning {table}: {e}")

def main():
    print("🧹 Tenant Duplicate Cleanup Script")
    print("=" * 50)
    
    # Get database connection
    conn = get_database_connection()
    conn.autocommit = False
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Find duplicate tenants
            print("🔍 Finding duplicate tenant names...")
            duplicates = find_duplicate_tenants(cursor)
            
            if not duplicates:
                print("✅ No duplicate tenant names found!")
                return
            
            print(f"⚠️ Found {len(duplicates)} tenant names with duplicates:")
            for dup in duplicates:
                print(f"   📋 '{dup['name']}': {dup['count']} instances (IDs: {dup['tenant_ids']})")
            
            print("\n🔧 Starting cleanup process...")
            
            for dup in duplicates:
                tenant_name = dup['name']
                tenant_ids = dup['tenant_ids']
                tenant_id_to_keep = min(tenant_ids)  # Keep the oldest (lowest ID)
                tenant_ids_to_remove = [tid for tid in tenant_ids if tid != tenant_id_to_keep]
                
                print(f"\n📋 Processing '{tenant_name}':")
                print(f"   ✅ Keeping tenant ID {tenant_id_to_keep}")
                print(f"   🗑️ Removing tenant IDs: {tenant_ids_to_remove}")
                
                # Clean up data for each duplicate tenant
                for tenant_id_to_remove in tenant_ids_to_remove:
                    cleanup_tenant_data(cursor, tenant_id_to_remove, tenant_id_to_keep)
                    
                    # Remove the duplicate tenant record
                    cursor.execute("DELETE FROM tenants WHERE id = %s;", (tenant_id_to_remove,))
                    print(f"   ✅ Removed duplicate tenant record ID {tenant_id_to_remove}")
            
            # Commit all changes
            conn.commit()
            print("\n✅ Cleanup completed successfully!")
            print("🎯 Database is now ready for UNIQUE constraint on tenant names.")
            
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during cleanup: {e}")
        print("🔄 All changes have been rolled back.")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
