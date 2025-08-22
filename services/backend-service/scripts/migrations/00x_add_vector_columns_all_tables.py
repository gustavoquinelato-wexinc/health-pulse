"""
Migration 002: Add Vector Columns for Strategic Business Intelligence Platform
Adds pgvector embedding columns to all 24 tables for comprehensive RAG implementation
Hackathon Implementation - All tables vectorized from Day 1
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

def get_database_connection():
    """Get database connection using environment variables"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5434"),
        database=os.getenv("DB_NAME", "health_pulse"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres")
    )

def apply(connection):
    """Add vector columns to all 24 tables for Strategic Business Intelligence Platform."""

    cursor = connection.cursor(cursor_factory=RealDictCursor)
    
    try:
        print("🚀 Starting Migration 002: Strategic Business Intelligence Platform")
        print("📋 Adding pgvector extension...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        print("📋 Adding vector columns to all 24 tables...")
        
        # All 24 tables with their embedding strategy
        vector_tables = {
            # Tier 1: Core Business Intelligence
            'clients': {
                'fields': ['name'],
                'description': 'Client context for multi-tenant intelligence'
            },
            'users': {
                'fields': ['first_name', 'last_name', 'email'],
                'description': 'Individual performance context and team composition'
            },
            'projects': {
                'fields': ['name', 'key'],
                'description': 'Project intelligence and cross-project analysis'
            },
            'issues': {
                'fields': ['summary', 'description', 'custom_field_01', 'custom_field_02'],
                'description': 'Main Jira intelligence - issue classification and complexity analysis'
            },
            
            # Tier 2: Development Intelligence
            'repositories': {
                'fields': ['name', 'full_name', 'description'],
                'description': 'Codebase intelligence and technology stack analysis'
            },
            'pull_requests': {
                'fields': ['title', 'body'],
                'description': 'Development intelligence - PR categorization and change impact'
            },
            'pull_request_comments': {
                'fields': ['body'],
                'description': 'Code review quality and individual contribution analysis'
            },
            'pull_request_reviews': {
                'fields': ['body'],
                'description': 'Review process analysis and rework indicators'
            },
            'pull_request_commits': {
                'fields': ['message'],
                'description': 'Rework detection and development patterns'
            },
            
            # Tier 3: Workflow & Process Intelligence
            'workflows': {
                'fields': ['step_name'],
                'description': 'Commitment point analysis and workflow optimization'
            },
            'issue_changelogs': {
                'fields': ['from_string', 'to_string'],
                'description': 'Lead time intelligence and cycle time analysis'
            },
            'statuses': {
                'fields': ['original_name', 'description'],
                'description': 'Status intelligence and workflow mapping'
            },
            'status_mappings': {
                'fields': ['status_from', 'status_to'],
                'description': 'Status standardization and process optimization'
            },
            'issuetypes': {
                'fields': ['original_name', 'description'],
                'description': 'Work classification and hierarchy understanding'
            },
            'issuetype_mappings': {
                'fields': ['issuetype_from', 'issuetype_to'],
                'description': 'Work type analysis and effort estimation'
            },
            'issuetype_hierarchies': {
                'fields': ['level_name', 'description'],
                'description': 'Work hierarchy analysis and organizational structure'
            },
            
            # Tier 4: Industry Benchmarking
            'dora_market_benchmarks': {
                'fields': ['metric_name', 'performance_tier'],
                'description': 'Industry standards and performance tier classification'
            },
            'dora_metric_insights': {
                'fields': ['insight_text'],
                'description': 'Industry intelligence and best practice recommendations'
            },
            
            # Tier 5: Relationship & Junction Intelligence
            'jira_pull_request_links': {
                'fields': ['branch_name', 'repo_full_name'],
                'description': 'Development traceability and flow mapping'
            },
            'projects_issuetypes': {
                'fields': ['composite_context'],
                'description': 'Project configuration intelligence'
            },
            'projects_statuses': {
                'fields': ['composite_context'],
                'description': 'Workflow standardization analysis'
            },
            
            # Tier 6: Organizational Context
            'user_permissions': {
                'fields': ['resource', 'action'],
                'description': 'RBAC intelligence and access control analysis'
            },
            'user_sessions': {
                'fields': ['session_metadata'],
                'description': 'Adoption analysis and user engagement patterns'
            },
            'system_settings': {
                'fields': ['setting_name', 'setting_value'],
                'description': 'System configuration intelligence'
            }
        }
        
        # Add vector columns to all tables
        for table, config in vector_tables.items():
            print(f"   📊 Adding vector column to {table}...")
            
            # Add vector column
            cursor.execute(f"""
                ALTER TABLE {table} 
                ADD COLUMN IF NOT EXISTS embedding vector(1536);
            """)
            
            # Add comment describing vectorization strategy
            field_list = ', '.join(config['fields'])
            cursor.execute(f"""
                COMMENT ON COLUMN {table}.embedding IS 
                'Strategic BI embedding of: {field_list}. {config["description"]}';
            """)
            
            print(f"   ✅ {table}: {config['description']}")
        
        print("📋 Creating HNSW indexes for fast similarity search...")
        
        # Create HNSW indexes for all tables
        for table in vector_tables.keys():
            index_name = f"idx_{table}_embedding_hnsw"
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {index_name} 
                ON {table} USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """)
            print(f"   🔍 Created HNSW index for {table}")
        
        print("📋 Recording migration in history...")
        
        # Record migration
        cursor.execute("""
            INSERT INTO migration_history (migration_number, migration_name, applied_at, status)
            VALUES ('002', 'Add Vector Columns for Strategic BI Platform', NOW(), 'applied')
            ON CONFLICT (migration_number)
            DO UPDATE SET applied_at = NOW(), status = 'applied', rollback_at = NULL;
        """)
        
        connection.commit()
        
        print("✅ Migration 002 completed successfully!")
        print(f"📊 Vectorized {len(vector_tables)} tables for Strategic Business Intelligence")
        print("🎯 Ready for WEX AI Gateway integration and structured text embeddings")
        
        return True
        
    except Exception as e:
        connection.rollback()
        print(f"❌ Error applying migration 002: {e}")
        raise e
    finally:
        cursor.close()

def rollback(connection):
    """Rollback migration by removing vector columns and indexes"""

    cursor = connection.cursor(cursor_factory=RealDictCursor)
    
    try:
        print("🔄 Rolling back Migration 002...")
        
        # List of all tables
        tables = [
            'clients', 'users', 'projects', 'issues', 'repositories',
            'pull_requests', 'pull_request_comments', 'pull_request_reviews', 'pull_request_commits',
            'workflows', 'issue_changelogs', 'statuses', 'status_mappings', 
            'issuetypes', 'issuetype_mappings', 'issuetype_hierarchies',
            'dora_market_benchmarks', 'dora_metric_insights',
            'jira_pull_request_links', 'projects_issuetypes', 'projects_statuses',
            'user_permissions', 'user_sessions', 'system_settings'
        ]
        
        # Drop indexes first
        for table in tables:
            index_name = f"idx_{table}_embedding_hnsw"
            cursor.execute(f"DROP INDEX IF EXISTS {index_name};")
        
        # Drop vector columns
        for table in tables:
            cursor.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS embedding;")
        
        # Update migration history
        cursor.execute("""
            UPDATE migration_history
            SET rollback_at = NOW(), status = 'rolled_back'
            WHERE migration_number = '002';
        """)
        
        connection.commit()
        print("✅ Migration 002 rolled back successfully!")
        
    except Exception as e:
        connection.rollback()
        print(f"❌ Error rolling back migration 002: {e}")
        raise e
    finally:
        cursor.close()

if __name__ == "__main__":
    import sys

    connection = get_database_connection()

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback(connection)
    else:
        apply(connection)

    connection.close()
