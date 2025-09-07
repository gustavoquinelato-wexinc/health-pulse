"""
Migration 0002: Add Missing Primary Keys and Foreign Key Constraints

This migration ensures all primary keys and foreign key constraints are properly added
to the database. It checks for existing constraints before adding them to avoid conflicts.

Run this if you notice missing FKs/PKs in your database tables.
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

def run_migration():
    """Add missing primary keys and foreign key constraints"""
    
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
    
    print("🔧 Starting Migration 0002: Add Missing Constraints")
    print(f"📡 Connecting to database: {db_config['host']}:{db_config['port']}/{db_config['database']}")
    
    try:
        # Connect to database
        conn = psycopg2.connect(**db_config)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("✅ Connected to database")
        
        # Helper function to check if constraint exists
        def constraint_exists(constraint_name: str, table_name: str, constraint_type: str) -> bool:
            cursor.execute("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = %s
                AND constraint_type = %s
                AND constraint_name = %s;
            """, (table_name, constraint_type, constraint_name))
            return cursor.fetchone() is not None
        
        # Helper function to add constraint if it doesn't exist
        def add_constraint_if_not_exists(constraint_name: str, table_name: str, constraint_definition: str, constraint_type: str = 'FOREIGN KEY'):
            if not constraint_exists(constraint_name, table_name, constraint_type):
                try:
                    cursor.execute(f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} {constraint_definition};")
                    print(f"✅ Added {constraint_type}: {constraint_name} to {table_name}")
                except Exception as e:
                    print(f"⚠️ Failed to add {constraint_type} {constraint_name} to {table_name}: {e}")
            else:
                print(f"⏭️ {constraint_type} {constraint_name} already exists on {table_name}")
        
        # Helper function to add primary key if it doesn't exist
        def ensure_primary_key(table_name: str, pk_name: str):
            if not constraint_exists(pk_name, table_name, 'PRIMARY KEY'):
                try:
                    cursor.execute(f"ALTER TABLE {table_name} ADD CONSTRAINT {pk_name} PRIMARY KEY (id);")
                    print(f"✅ Added PRIMARY KEY: {pk_name} to {table_name}")
                except Exception as e:
                    print(f"⚠️ Failed to add PRIMARY KEY {pk_name} to {table_name}: {e}")
            else:
                print(f"⏭️ PRIMARY KEY {pk_name} already exists on {table_name}")
        
        print("\n📋 Adding missing PRIMARY KEY constraints...")
        
        # Core tables
        ensure_primary_key('tenants', 'pk_tenants')
        ensure_primary_key('users', 'pk_users')
        ensure_primary_key('user_sessions', 'pk_user_sessions')
        ensure_primary_key('user_permissions', 'pk_user_permissions')
        ensure_primary_key('integrations', 'pk_integrations')
        ensure_primary_key('projects', 'pk_projects')
        ensure_primary_key('workflows', 'pk_workflows')
        ensure_primary_key('status_mappings', 'pk_status_mappings')
        ensure_primary_key('wits_hierarchies', 'pk_wits_hierarchies')
        ensure_primary_key('wits_mappings', 'pk_wits_mappings')
        ensure_primary_key('wits', 'pk_wits')
        ensure_primary_key('statuses', 'pk_statuses')
        ensure_primary_key('work_items', 'pk_work_items')
        ensure_primary_key('changelogs', 'pk_changelogs')
        ensure_primary_key('repositories', 'pk_repositories')
        ensure_primary_key('prs', 'pk_prs')
        ensure_primary_key('prs_reviews', 'pk_prs_reviews')
        ensure_primary_key('prs_commits', 'pk_prs_commits')
        ensure_primary_key('prs_comments', 'pk_prs_comments')
        ensure_primary_key('system_settings', 'pk_system_settings')
        ensure_primary_key('job_schedules', 'pk_job_schedules')
        ensure_primary_key('wits_prs_links', 'pk_wits_prs_links')
        ensure_primary_key('tenant_colors', 'pk_tenant_colors')
        ensure_primary_key('qdrant_vectors', 'pk_qdrant_vectors')
        ensure_primary_key('ai_usage_trackings', 'pk_ai_usage_trackings')
        ensure_primary_key('ai_learning_memories', 'pk_ai_learning_memories')
        ensure_primary_key('ai_predictions', 'pk_ai_predictions')
        ensure_primary_key('ai_performance_metrics', 'pk_ai_performance_metrics')
        ensure_primary_key('ml_anomaly_alerts', 'pk_ml_anomaly_alerts')
        
        print("\n📋 Adding missing FOREIGN KEY constraints...")
        
        # Core table foreign keys
        add_constraint_if_not_exists('fk_users_tenant_id', 'users', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_user_sessions_user_id', 'user_sessions', 'FOREIGN KEY (user_id) REFERENCES users(id)')
        add_constraint_if_not_exists('fk_user_sessions_tenant_id', 'user_sessions', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_user_permissions_user_id', 'user_permissions', 'FOREIGN KEY (user_id) REFERENCES users(id)')
        add_constraint_if_not_exists('fk_user_permissions_tenant_id', 'user_permissions', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        
        # Integrations and projects
        add_constraint_if_not_exists('fk_integrations_tenant_id', 'integrations', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_integrations_fallback', 'integrations', 'FOREIGN KEY (fallback_integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_projects_integration_id', 'projects', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_projects_tenant_id', 'projects', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        
        # Workflow and mappings
        add_constraint_if_not_exists('fk_workflows_tenant_id', 'workflows', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_workflows_integration_id', 'workflows', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_status_mappings_workflow_id', 'status_mappings', 'FOREIGN KEY (workflow_id) REFERENCES workflows(id)')
        add_constraint_if_not_exists('fk_status_mappings_tenant_id', 'status_mappings', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_status_mappings_integration_id', 'status_mappings', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_wits_hierarchies_tenant_id', 'wits_hierarchies', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_wits_hierarchies_integration_id', 'wits_hierarchies', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_wits_mappings_tenant_id', 'wits_mappings', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_wits_mappings_integration_id', 'wits_mappings', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_wits_mappings_hierarchy_id', 'wits_mappings', 'FOREIGN KEY (wits_hierarchy_id) REFERENCES wits_hierarchies(id)')
        
        # WITs and statuses
        add_constraint_if_not_exists('fk_wits_integration_id', 'wits', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_wits_wits_mapping_id', 'wits', 'FOREIGN KEY (wits_mapping_id) REFERENCES wits_mappings(id)')
        add_constraint_if_not_exists('fk_wits_tenant_id', 'wits', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_statuses_integration_id', 'statuses', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_statuses_status_mapping_id', 'statuses', 'FOREIGN KEY (status_mapping_id) REFERENCES status_mappings(id)')
        add_constraint_if_not_exists('fk_statuses_tenant_id', 'statuses', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')

        # Work items and changelogs
        add_constraint_if_not_exists('fk_work_items_integration_id', 'work_items', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_work_items_project_id', 'work_items', 'FOREIGN KEY (project_id) REFERENCES projects(id)')
        add_constraint_if_not_exists('fk_work_items_wit_id', 'work_items', 'FOREIGN KEY (wit_id) REFERENCES wits(id)')
        add_constraint_if_not_exists('fk_work_items_status_id', 'work_items', 'FOREIGN KEY (status_id) REFERENCES statuses(id)')
        add_constraint_if_not_exists('fk_work_items_tenant_id', 'work_items', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')

        # Work item changelogs
        add_constraint_if_not_exists('fk_changelogs_integration_id', 'changelogs', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_changelogs_work_item_id', 'changelogs', 'FOREIGN KEY (work_item_id) REFERENCES work_items(id)')
        add_constraint_if_not_exists('fk_changelogs_from_status_id', 'changelogs', 'FOREIGN KEY (from_status_id) REFERENCES statuses(id)')
        add_constraint_if_not_exists('fk_changelogs_to_status_id', 'changelogs', 'FOREIGN KEY (to_status_id) REFERENCES statuses(id)')
        add_constraint_if_not_exists('fk_changelogs_tenant_id', 'changelogs', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')

        # Repositories and PRs
        add_constraint_if_not_exists('fk_repositories_tenant_id', 'repositories', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_repositories_integration_id', 'repositories', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_prs_repository_id', 'prs', 'FOREIGN KEY (repository_id) REFERENCES repositories(id)')
        add_constraint_if_not_exists('fk_prs_work_item_id', 'prs', 'FOREIGN KEY (work_item_id) REFERENCES work_items(id)')
        add_constraint_if_not_exists('fk_prs_tenant_id', 'prs', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_prs_integration_id', 'prs', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')

        # PR related tables
        add_constraint_if_not_exists('fk_prs_reviews_pr_id', 'prs_reviews', 'FOREIGN KEY (pr_id) REFERENCES prs(id)')
        add_constraint_if_not_exists('fk_prs_reviews_tenant_id', 'prs_reviews', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_prs_reviews_integration_id', 'prs_reviews', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_prs_commits_pr_id', 'prs_commits', 'FOREIGN KEY (pr_id) REFERENCES prs(id)')
        add_constraint_if_not_exists('fk_prs_commits_tenant_id', 'prs_commits', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_prs_commits_integration_id', 'prs_commits', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_prs_comments_pr_id', 'prs_comments', 'FOREIGN KEY (pr_id) REFERENCES prs(id)')
        add_constraint_if_not_exists('fk_prs_comments_tenant_id', 'prs_comments', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_prs_comments_integration_id', 'prs_comments', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')

        # System tables
        add_constraint_if_not_exists('fk_system_settings_tenant_id', 'system_settings', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_job_schedules_tenant_id', 'job_schedules', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_job_schedules_integration_id', 'job_schedules', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_wits_prs_links_work_item_id', 'wits_prs_links', 'FOREIGN KEY (work_item_id) REFERENCES work_items(id)')
        add_constraint_if_not_exists('fk_wits_prs_links_tenant_id', 'wits_prs_links', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_wits_prs_links_integration_id', 'wits_prs_links', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')

        # Color table foreign key
        add_constraint_if_not_exists('fk_tenant_colors_tenant_id', 'tenant_colors', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')

        # Phase 3-1: New table foreign keys
        add_constraint_if_not_exists('fk_qdrant_vectors_tenant_id', 'qdrant_vectors', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')
        add_constraint_if_not_exists('fk_ai_usage_trackings_tenant_id', 'ai_usage_trackings', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')
        add_constraint_if_not_exists('fk_ai_learning_memories_tenant_id', 'ai_learning_memories', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')
        add_constraint_if_not_exists('fk_ai_predictions_tenant_id', 'ai_predictions', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')
        add_constraint_if_not_exists('fk_ai_performance_metrics_tenant_id', 'ai_performance_metrics', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')
        add_constraint_if_not_exists('fk_ml_anomaly_alerts_tenant_id', 'ml_anomaly_alerts', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')

        # Relationship tables (many-to-many)
        add_constraint_if_not_exists('fk_projects_wits_project_id', 'projects_wits', 'FOREIGN KEY (project_id) REFERENCES projects(id)')
        add_constraint_if_not_exists('fk_projects_wits_wit_id', 'projects_wits', 'FOREIGN KEY (wit_id) REFERENCES wits(id)')
        add_constraint_if_not_exists('fk_projects_statuses_project_id', 'projects_statuses', 'FOREIGN KEY (project_id) REFERENCES projects(id)')
        add_constraint_if_not_exists('fk_projects_statuses_status_id', 'projects_statuses', 'FOREIGN KEY (status_id) REFERENCES statuses(id)')

        print("\n✅ Migration 0002 completed successfully!")
        print("🔧 All missing primary keys and foreign key constraints have been added.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()
            print("📡 Database connection closed")

if __name__ == "__main__":
    run_migration()
