"""
Database Constraint Checker

This script checks which primary keys and foreign key constraints are missing
from your database tables and provides a summary.
"""

import psycopg2
import os
from dotenv import load_dotenv

def check_constraints():
    """Check which constraints are missing from the database"""
    
    # Load environment variables
    load_dotenv()
    
    # Database connection
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'health_pulse'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres')
    }
    
    print("🔍 Checking Database Constraints")
    print(f"📡 Connecting to database: {db_config['host']}:{db_config['port']}/{db_config['database']}")
    
    try:
        # Connect to database
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        print("✅ Connected to database")
        
        # Expected primary keys
        expected_primary_keys = [
            ('tenants', 'pk_tenants'),
            ('users', 'pk_users'),
            ('user_sessions', 'pk_user_sessions'),
            ('user_permissions', 'pk_user_permissions'),
            ('integrations', 'pk_integrations'),
            ('projects', 'pk_projects'),
            ('workflows', 'pk_workflows'),
            ('status_mappings', 'pk_status_mappings'),
            ('wits_hierarchies', 'pk_wits_hierarchies'),
            ('wits_mappings', 'pk_wits_mappings'),
            ('wits', 'pk_wits'),
            ('statuses', 'pk_statuses'),
            ('work_items', 'pk_work_items'),
            ('changelogs', 'pk_changelogs'),
            ('repositories', 'pk_repositories'),
            ('prs', 'pk_prs'),
            ('prs_reviews', 'pk_prs_reviews'),
            ('prs_commits', 'pk_prs_commits'),
            ('prs_comments', 'pk_prs_comments'),
            ('system_settings', 'pk_system_settings'),
            ('job_schedules', 'pk_job_schedules'),
            ('wits_prs_links', 'pk_wits_prs_links'),
            ('tenant_colors', 'pk_tenant_colors'),
            ('qdrant_vectors', 'pk_qdrant_vectors'),
            ('ai_usage_trackings', 'pk_ai_usage_trackings'),
            ('ai_learning_memories', 'pk_ai_learning_memories'),
            ('ai_predictions', 'pk_ai_predictions'),
            ('ai_performance_metrics', 'pk_ai_performance_metrics'),
            ('ml_anomaly_alerts', 'pk_ml_anomaly_alerts')
        ]
        
        # Expected foreign keys (table, constraint_name, description)
        expected_foreign_keys = [
            ('users', 'fk_users_tenant_id', 'tenant_id -> tenants(id)'),
            ('user_sessions', 'fk_user_sessions_user_id', 'user_id -> users(id)'),
            ('user_sessions', 'fk_user_sessions_tenant_id', 'tenant_id -> tenants(id)'),
            ('integrations', 'fk_integrations_tenant_id', 'tenant_id -> tenants(id)'),
            ('projects', 'fk_projects_integration_id', 'integration_id -> integrations(id)'),
            ('projects', 'fk_projects_tenant_id', 'tenant_id -> tenants(id)'),
            ('wits', 'fk_wits_integration_id', 'integration_id -> integrations(id)'),
            ('wits', 'fk_wits_wits_mapping_id', 'wits_mapping_id -> wits_mappings(id)'),
            ('wits', 'fk_wits_tenant_id', 'tenant_id -> tenants(id)'),
            ('statuses', 'fk_statuses_integration_id', 'integration_id -> integrations(id)'),
            ('statuses', 'fk_statuses_tenant_id', 'tenant_id -> tenants(id)'),
            ('work_items', 'fk_work_items_integration_id', 'integration_id -> integrations(id)'),
            ('work_items', 'fk_work_items_project_id', 'project_id -> projects(id)'),
            ('work_items', 'fk_work_items_wit_id', 'wit_id -> wits(id)'),
            ('work_items', 'fk_work_items_status_id', 'status_id -> statuses(id)'),
            ('work_items', 'fk_work_items_tenant_id', 'tenant_id -> tenants(id)'),
            ('changelogs', 'fk_changelogs_integration_id', 'integration_id -> integrations(id)'),
            ('changelogs', 'fk_changelogs_work_item_id', 'work_item_id -> work_items(id)'),
            ('changelogs', 'fk_changelogs_from_status_id', 'from_status_id -> statuses(id)'),
            ('changelogs', 'fk_changelogs_to_status_id', 'to_status_id -> statuses(id)'),
            ('changelogs', 'fk_changelogs_tenant_id', 'tenant_id -> tenants(id)'),
            ('job_schedules', 'fk_job_schedules_tenant_id', 'tenant_id -> tenants(id)'),
            ('job_schedules', 'fk_job_schedules_integration_id', 'integration_id -> integrations(id)')
        ]
        
        # Check primary keys
        print("\n📋 Checking PRIMARY KEY constraints...")
        missing_primary_keys = []
        
        for table_name, pk_name in expected_primary_keys:
            cursor.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = %s
                AND constraint_type = 'PRIMARY KEY'
                AND constraint_name = %s;
            """, (table_name, pk_name))
            
            if not cursor.fetchone():
                missing_primary_keys.append((table_name, pk_name))
            else:
                print(f"✅ {table_name}.{pk_name}")
        
        if missing_primary_keys:
            print(f"\n❌ Missing {len(missing_primary_keys)} PRIMARY KEY constraints:")
            for table_name, pk_name in missing_primary_keys:
                print(f"   ⚠️ {table_name}.{pk_name}")
        else:
            print("\n✅ All PRIMARY KEY constraints are present!")
        
        # Check foreign keys
        print("\n📋 Checking FOREIGN KEY constraints...")
        missing_foreign_keys = []
        
        for table_name, fk_name, description in expected_foreign_keys:
            cursor.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = %s
                AND constraint_type = 'FOREIGN KEY'
                AND constraint_name = %s;
            """, (table_name, fk_name))
            
            if not cursor.fetchone():
                missing_foreign_keys.append((table_name, fk_name, description))
            else:
                print(f"✅ {table_name}.{fk_name}")
        
        if missing_foreign_keys:
            print(f"\n❌ Missing {len(missing_foreign_keys)} FOREIGN KEY constraints:")
            for table_name, fk_name, description in missing_foreign_keys:
                print(f"   ⚠️ {table_name}.{fk_name} ({description})")
        else:
            print("\n✅ All FOREIGN KEY constraints are present!")
        
        # Summary
        total_missing = len(missing_primary_keys) + len(missing_foreign_keys)
        if total_missing > 0:
            print(f"\n📊 SUMMARY: {total_missing} constraints are missing from your database")
            print("🔧 Run the migration script to add them:")
            print("   python services/backend-service/scripts/migrations/0002_add_missing_constraints.py")
        else:
            print("\n🎉 All constraints are properly configured!")
        
    except Exception as e:
        print(f"❌ Error checking constraints: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()
            print("📡 Database connection closed")

if __name__ == "__main__":
    check_constraints()
