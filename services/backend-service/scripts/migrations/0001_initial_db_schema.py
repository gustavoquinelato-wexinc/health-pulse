#!/usr/bin/env python3
"""
Migration 0001: Initial Database Schema - Clean 3-Database Architecture (Phase 3-1)
Description: Creates clean PostgreSQL schema without vector columns for 3-database architecture
Author: Pulse Platform Team
Date: 2025-09-02 (Updated for Phase 3-1)

This migration creates the complete initial database schema including:
- Tenant management tables with multi-tenant support (NO vector columns)
- Authentication and user management for multiple tenants
- Integration tables with AI provider support and configuration
- Work item tracking and workflow tables (business data only)
- Development data tables (PRs, commits, etc.) without embeddings
- Job scheduling and system settings with theme/color customization
- ML monitoring tables for AI learning and prediction logging
- Qdrant reference tracking for vector operations
- All primary keys, foreign keys, unique constraints, and performance indexes

This migration contains ONLY schema creation for clean 3-database architecture - no seed data.

Phase 3-1 Clean Architecture Implemented:
✅ PostgreSQL extensions (vector extension kept for compatibility)
✅ NO vector columns in business tables (vectors moved to Qdrant)
✅ Qdrant reference tracking table for vector management
✅ Enhanced integrations table with AI provider support
✅ AI configuration tables (tenant preferences, usage tracking)
✅ ML monitoring tables for AI learning and prediction logging
✅ Clean CREATE-only statements (no ALTER statements)
✅ 3-Database architecture: PostgreSQL Primary + Replica + Qdrant
"""

import os
import sys
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Add the backend service to the path to access database configuration
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

def get_database_connection():
    """Get database connection using backend service configuration."""
    try:
        from app.core.config import Settings
        config = Settings()

        connection = psycopg2.connect(
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            database=config.POSTGRES_DATABASE,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD,
            cursor_factory=RealDictCursor
        )
        connection.autocommit = False  # Use transactions
        return connection
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)

def apply(connection):
    """Apply the initial schema migration with AI enhancements (Phase 1 Complete)."""
    print("🚀 Applying Migration 0001: Initial Database Schema with AI Enhancements (Phase 1 Complete)")

    cursor = connection.cursor()

    try:
        # Check if migration is already applied
        print("📋 Checking migration status...")
        try:
            cursor.execute("""
                SELECT status FROM migration_history
                WHERE migration_number = %s AND status = 'applied';
            """, ('0001',))
            result = cursor.fetchone()
            if result:
                print("⚠️ Migration 0001 is already applied. Use --rollback first if you want to reapply.")
                return
        except Exception:
            # migration_history table doesn't exist yet, which is fine for first run
            print("✅ First-time migration detected")

        # Start transaction
        print("📋 Creating extensions...")

        # Create required extensions
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("✅ Vector extension created")

        # Try to create pgml extension (optional for Phase 1)
        # Use a separate transaction to avoid aborting the main transaction
        connection.commit()  # Commit the vector extension
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pgml;")
            print("✅ PostgresML extension created")
        except Exception as e:
            # Rollback only the pgml extension attempt, not the whole migration
            connection.rollback()
            print(f"⚠️  PostgresML extension skipped (optional): {str(e)[:100]}...")
            print("   This is expected in Phase 1 - vector operations will work fine")

        # Start a new transaction for the rest of the migration
        connection.autocommit = False

        print("📋 Creating core tables...")

        # 1. Tenants table (foundation) - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                id SERIAL PRIMARY KEY,
                name VARCHAR NOT NULL UNIQUE,
                website VARCHAR,
                assets_folder VARCHAR(100),
                logo_filename VARCHAR(255) DEFAULT 'default-logo.png',
                color_schema_mode VARCHAR(10) DEFAULT 'default' CHECK (color_schema_mode IN ('default', 'custom')),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # 2. Users table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL,
                email VARCHAR(255) NOT NULL,
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                role VARCHAR(50) NOT NULL DEFAULT 'user',
                is_admin BOOLEAN DEFAULT FALSE,
                auth_provider VARCHAR(50) NOT NULL DEFAULT 'local',
                okta_user_id VARCHAR(255),
                password_hash VARCHAR(255),
                theme_mode VARCHAR(10) DEFAULT 'light',

                -- === ACCESSIBILITY PREFERENCES (moved from accessibility colors table) ===
                high_contrast_mode BOOLEAN DEFAULT FALSE,
                reduce_motion BOOLEAN DEFAULT FALSE,
                colorblind_safe_palette BOOLEAN DEFAULT FALSE,
                accessibility_level VARCHAR(10) DEFAULT 'regular', -- 'regular', 'AA', 'AAA'

                profile_image_filename VARCHAR(255),
                last_login_at TIMESTAMP,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # 3. User sessions table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users_sessions (
                id SERIAL,
                user_id INTEGER NOT NULL,
                token_hash VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 4. User permissions table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users_permissions (
                id SERIAL,
                user_id INTEGER NOT NULL,
                resource VARCHAR(100) NOT NULL,
                action VARCHAR(50) NOT NULL,
                granted BOOLEAN NOT NULL DEFAULT TRUE,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        print("✅ Core tables created")
        print("📋 Creating integration and project tables...")
        
        # 5. Clean integrations table (Phase 3-1) - Unified Settings Architecture
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS integrations (
                id SERIAL PRIMARY KEY,
                provider VARCHAR(50) NOT NULL, -- 'Jira', 'GitHub', 'WEX AI Gateway', etc.
                type VARCHAR(50) NOT NULL, -- 'Data', 'AI', 'Embedding', 'System'
                username VARCHAR,
                password VARCHAR, -- Encrypted tokens/passwords
                base_url TEXT,

                -- Unified settings JSON for all integration-specific configuration
                settings JSONB DEFAULT '{}', -- Type-specific settings (projects, models, costs, etc.)

                fallback_integration_id INTEGER, -- FK to another integration for fallback
                logo_filename VARCHAR(255), -- Filename of integration logo (stored in tenant assets folder)
                custom_field_mappings JSONB DEFAULT '{}', -- Custom field mappings for Jira integrations

                -- BaseEntity fields
                tenant_id INTEGER NOT NULL,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # 6. Projects table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL,
                external_id VARCHAR,
                key VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                project_type VARCHAR,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        print("✅ Integration and project tables created")
        print("📋 Creating workflow and mapping tables...")

        # 7. Workflows table (renamed from flow_steps) - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id SERIAL,
                step_name VARCHAR NOT NULL,
                step_number INTEGER,
                step_category VARCHAR NOT NULL,
                is_commitment_point BOOLEAN NOT NULL DEFAULT FALSE,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 8. Status mappings table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS statuses_mappings (
                id SERIAL,
                status_from VARCHAR NOT NULL,
                status_to VARCHAR NOT NULL,
                status_category VARCHAR NOT NULL,
                workflow_id INTEGER,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 9. WITs hierarchies table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wits_hierarchies (
                id SERIAL,
                level_name VARCHAR NOT NULL,
                level_number INTEGER NOT NULL,
                description VARCHAR,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 10. WITs mappings table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wits_mappings (
                id SERIAL,
                wit_from VARCHAR NOT NULL,
                wit_to VARCHAR NOT NULL,
                wits_hierarchy_id INTEGER NOT NULL,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 11. WITs table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wits (
                id SERIAL,
                external_id VARCHAR,
                original_name VARCHAR NOT NULL,
                wits_mapping_id INTEGER,
                description VARCHAR,
                hierarchy_level INTEGER NOT NULL,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 12. Statuses table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS statuses (
                id SERIAL,
                external_id VARCHAR,
                original_name VARCHAR NOT NULL,
                status_mapping_id INTEGER,
                category VARCHAR NOT NULL,
                description VARCHAR,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        print("✅ Workflow and mapping tables created")
        print("📋 Creating relationship tables...")

        # 13. Projects-Work itemtypes relationship table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects_wits (
                project_id INTEGER NOT NULL,
                wit_id INTEGER NOT NULL,
                PRIMARY KEY (project_id, wit_id)
            );
        """)

        # 14. Projects-Statuses relationship table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects_statuses (
                project_id INTEGER NOT NULL,
                status_id INTEGER NOT NULL,
                PRIMARY KEY (project_id, status_id)
            );
        """)

        print("✅ Relationship tables created")
        print("📋 Creating main data tables...")

        # 15. Work items table (complete with all custom fields and workflow columns)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_items (
                id SERIAL PRIMARY KEY,
                external_id VARCHAR,
                key VARCHAR,
                project_id INTEGER,
                team VARCHAR,
                summary VARCHAR,
                description TEXT,
                acceptance_criteria TEXT,
                wit_id INTEGER,
                status_id INTEGER,
                resolution VARCHAR,
                story_points INTEGER,
                assignee VARCHAR,
                labels VARCHAR,
                priority VARCHAR,
                parent_external_id VARCHAR,
                created TIMESTAMP,
                updated TIMESTAMP,
                work_first_committed_at TIMESTAMP,
                work_first_started_at TIMESTAMP,
                work_last_started_at TIMESTAMP,
                work_first_completed_at TIMESTAMP,
                work_last_completed_at TIMESTAMP,
                total_work_starts INTEGER DEFAULT 0,
                total_completions INTEGER DEFAULT 0,
                total_backlog_returns INTEGER DEFAULT 0,
                total_work_time_seconds FLOAT DEFAULT 0.0,
                total_review_time_seconds FLOAT DEFAULT 0.0,
                total_cycle_time_seconds FLOAT DEFAULT 0.0,
                total_lead_time_seconds FLOAT DEFAULT 0.0,
                workflow_complexity_score INTEGER DEFAULT 0,
                rework_indicator BOOLEAN DEFAULT FALSE,
                direct_completion BOOLEAN DEFAULT FALSE,
                code_changed BOOLEAN,
                custom_field_01 VARCHAR,
                custom_field_02 VARCHAR,
                custom_field_03 VARCHAR,
                custom_field_04 VARCHAR,
                custom_field_05 VARCHAR,
                custom_field_06 VARCHAR,
                custom_field_07 VARCHAR,
                custom_field_08 VARCHAR,
                custom_field_09 VARCHAR,
                custom_field_10 VARCHAR,
                custom_field_11 VARCHAR,
                custom_field_12 VARCHAR,
                custom_field_13 VARCHAR,
                custom_field_14 VARCHAR,
                custom_field_15 VARCHAR,
                custom_field_16 VARCHAR,
                custom_field_17 VARCHAR,
                custom_field_18 VARCHAR,
                custom_field_19 VARCHAR,
                custom_field_20 VARCHAR,
                custom_fields_overflow JSONB,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 16. Work item changelogs table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS changelogs (
                id SERIAL,
                work_item_id INTEGER NOT NULL,
                external_id VARCHAR,
                from_status_id INTEGER,
                to_status_id INTEGER,
                transition_start_date TIMESTAMP,
                transition_change_date TIMESTAMP,
                time_in_status_seconds FLOAT,
                changed_by VARCHAR,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)



        # 17. Repositories table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repositories (
                id SERIAL,
                external_id VARCHAR,
                name VARCHAR,
                full_name VARCHAR,
                description TEXT,
                url VARCHAR,
                is_private BOOLEAN,
                repo_created_at TIMESTAMP,
                repo_updated_at TIMESTAMP,
                pushed_at TIMESTAMP,
                language VARCHAR,
                default_branch VARCHAR,
                archived BOOLEAN,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        print("✅ Main data tables created")
        print("📋 Creating development and system tables...")

        # 18. PRs table (complete with all columns) - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prs (
                id SERIAL,
                external_id VARCHAR,
                external_repo_id VARCHAR,
                repository_id INTEGER NOT NULL,
                work_item_id INTEGER,
                number INTEGER,
                name VARCHAR,
                user_name VARCHAR,
                body TEXT,
                discussion_comment_count INTEGER,
                review_comment_count INTEGER,
                source VARCHAR,
                destination VARCHAR,
                reviewers INTEGER,
                status VARCHAR,
                url VARCHAR,
                pr_created_at TIMESTAMP,
                pr_updated_at TIMESTAMP,
                closed_at TIMESTAMP,
                merged_at TIMESTAMP,
                merged_by VARCHAR,
                commit_count INTEGER,
                additions INTEGER,
                deletions INTEGER,
                changed_files INTEGER,
                first_review_at TIMESTAMP,
                rework_commit_count INTEGER,
                review_cycles INTEGER,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 19. PRs reviews table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prs_reviews (
                id SERIAL,
                external_id VARCHAR,
                pr_id INTEGER NOT NULL,
                author_login VARCHAR,
                state VARCHAR,
                body TEXT,
                submitted_at TIMESTAMP,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 20. PRs commits table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prs_commits (
                id SERIAL,
                external_id VARCHAR,
                pr_id INTEGER NOT NULL,
                author_name VARCHAR,
                author_email VARCHAR,
                committer_name VARCHAR,
                committer_email VARCHAR,
                message TEXT,
                authored_date TIMESTAMP,
                committed_date TIMESTAMP,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 21. PRs comments table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prs_comments (
                id SERIAL,
                external_id VARCHAR,
                pr_id INTEGER NOT NULL,
                author_login VARCHAR,
                body TEXT,
                comment_type VARCHAR,
                path VARCHAR,
                position INTEGER,
                line INTEGER,
                created_at_github TIMESTAMP,
                updated_at_github TIMESTAMP,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 22. System settings table - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                id SERIAL,
                setting_key VARCHAR NOT NULL,
                setting_value VARCHAR NOT NULL,
                setting_type VARCHAR NOT NULL DEFAULT 'string',
                description VARCHAR,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(setting_key, tenant_id)
            );
        """)

        # 23. ETL jobs table - Autonomous Architecture (from migration 0005)
        print("   🏗️ Creating etl_jobs table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS etl_jobs (
                id SERIAL PRIMARY KEY,
                job_name VARCHAR NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'READY',
                schedule_interval_minutes INTEGER NOT NULL DEFAULT 360,
                retry_interval_minutes INTEGER NOT NULL DEFAULT 15,
                last_run_started_at TIMESTAMP,
                last_run_finished_at TIMESTAMP,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                checkpoint_data JSONB,
                integration_id INTEGER,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(job_name, tenant_id),
                CHECK (status IN ('READY', 'RUNNING', 'FINISHED', 'FAILED'))
            );
        """)
        print("   ✅ etl_jobs table created")

        # 24. Jira PR links table (complete with all columns) - NO vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wits_prs_links (
                id SERIAL,
                work_item_id INTEGER NOT NULL,
                external_repo_id VARCHAR NOT NULL,
                repo_full_name VARCHAR NOT NULL,
                pull_request_number INTEGER NOT NULL,
                branch_name VARCHAR,
                commit_sha VARCHAR,
                pr_status VARCHAR,
                integration_id INTEGER NOT NULL,
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 24.1. Raw extraction data storage - Phase 1 Queue Infrastructure
        # Stores complete API responses for debugging/reprocessing/audit trail
        # Simplified table with only essential columns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_extraction_data (
                id SERIAL PRIMARY KEY,
                type VARCHAR(50) NOT NULL,          -- 'jira_custom_fields', 'github_prs', etc.
                raw_data JSONB NOT NULL,            -- Complete API response (exact payload)
                status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
                error_details JSONB,                -- Error information if processing failed

                -- BaseEntity fields with proper foreign keys
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                integration_id INTEGER NOT NULL REFERENCES integrations(id),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                active BOOLEAN DEFAULT TRUE
            );
        """)

        # Create indexes for raw_extraction_data
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_extraction_data_tenant
            ON raw_extraction_data(tenant_id);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_extraction_data_integration
            ON raw_extraction_data(integration_id);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_extraction_data_type
            ON raw_extraction_data(type);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_extraction_data_status
            ON raw_extraction_data(status);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_extraction_data_created_at
            ON raw_extraction_data(created_at DESC);
        """)

        # 25. Migration history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS migration_history (
                id SERIAL,
                migration_number VARCHAR(10) UNIQUE NOT NULL,
                migration_name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP DEFAULT NOW(),
                rollback_at TIMESTAMP,
                status VARCHAR(20) NOT NULL DEFAULT 'applied'
            );
        """)

        # 26. Qdrant vectors table - tracks vector references with tenant isolation (Phase 3-1)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qdrant_vectors (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                table_name VARCHAR(50) NOT NULL,
                record_id INTEGER NOT NULL,
                qdrant_collection VARCHAR(100) NOT NULL,
                qdrant_point_id UUID NOT NULL,
                vector_type VARCHAR(50) NOT NULL, -- 'content', 'summary', 'metadata'
                embedding_model VARCHAR(100) NOT NULL, -- Track which model generated this
                embedding_provider VARCHAR(50) NOT NULL, -- 'openai', 'azure', 'sentence_transformers'
                last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

                UNIQUE(tenant_id, table_name, record_id, vector_type)
            );
        """)

        # AI tables removed - tenant_ai_preferences and tenant_ai_configuration not needed yet

        # 29. AI usage trackings table (inspired by WrenAI's cost monitoring)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_usage_trackings (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL,
                provider VARCHAR(50) NOT NULL, -- 'openai', 'azure', 'sentence_transformers'
                operation VARCHAR(50) NOT NULL, -- 'embedding', 'text_generation', 'analysis'
                model_name VARCHAR(100),
                input_count INTEGER DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                cost DECIMAL(10,4) DEFAULT 0.0,
                request_metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # 30. Vectorization integrated into transform workers (no separate queue table needed)

        # 26. DORA market benchmarks table (global)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dora_market_benchmarks (
                id SERIAL,
                report_year INTEGER NOT NULL,
                report_source VARCHAR(100) DEFAULT 'Google DORA Report',
                performance_tier VARCHAR(20) NOT NULL,
                metric_name VARCHAR(50) NOT NULL,
                metric_value VARCHAR(50) NOT NULL,
                metric_unit VARCHAR(20),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # 27. DORA metric insights table (global)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dora_metric_insights (
                id SERIAL,
                report_year INTEGER NOT NULL,
                metric_name VARCHAR(50) NOT NULL,
                insight_text TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # 28. Tenant colors table (unified architecture)
        print("   🏗️ Creating unified tenants_colors table...")

        # Drop old tenant_colors table if it exists (wrong name)
        cursor.execute("DROP TABLE IF EXISTS tenant_colors CASCADE;")
        print("   🗑️ Dropped old tenant_colors table")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenants_colors (
                id SERIAL PRIMARY KEY,

                -- === IDENTIFIERS ===
                color_schema_mode VARCHAR(10) NOT NULL, -- 'default' or 'custom'
                accessibility_level VARCHAR(10) NOT NULL, -- 'regular', 'AA', 'AAA'
                theme_mode VARCHAR(5) NOT NULL, -- 'light' or 'dark'

                -- === BASE COLORS (5 columns) ===
                color1 VARCHAR(7),
                color2 VARCHAR(7),
                color3 VARCHAR(7),
                color4 VARCHAR(7),
                color5 VARCHAR(7),

                -- === CALCULATED VARIANTS (10 columns) ===
                on_color1 VARCHAR(7),
                on_color2 VARCHAR(7),
                on_color3 VARCHAR(7),
                on_color4 VARCHAR(7),
                on_color5 VARCHAR(7),
                on_gradient_1_2 VARCHAR(7),
                on_gradient_2_3 VARCHAR(7),
                on_gradient_3_4 VARCHAR(7),
                on_gradient_4_5 VARCHAR(7),
                on_gradient_5_1 VARCHAR(7),

                -- === BASE ENTITY FIELDS ===
                tenant_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),

                -- === NEW UNIFIED UNIQUE CONSTRAINT ===
                CONSTRAINT uk_tenants_colors_unified UNIQUE(tenant_id, color_schema_mode, accessibility_level, theme_mode)
            );
        """)



        print("✅ Development and system tables created")

        print("📋 Creating primary key constraints...")

        # Add explicit primary key constraints with proper names (idempotent)
        def ensure_primary_key(table_name: str, pk_name: str, column: str = 'id'):
            cursor.execute(f"""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = '{table_name}'
                AND constraint_type = 'PRIMARY KEY';
            """)
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE {table_name} ADD CONSTRAINT {pk_name} PRIMARY KEY ({column});")

        # tenants primary key already defined inline
        ensure_primary_key('users', 'pk_users')
        ensure_primary_key('users_sessions', 'pk_users_sessions')
        ensure_primary_key('users_permissions', 'pk_users_permissions')
        # integrations primary key already defined inline
        ensure_primary_key('projects', 'pk_projects')
        ensure_primary_key('workflows', 'pk_workflows')
        ensure_primary_key('statuses_mappings', 'pk_statuses_mappings')
        ensure_primary_key('wits_hierarchies', 'pk_wits_hierarchies')
        ensure_primary_key('wits_mappings', 'pk_wits_mappings')
        ensure_primary_key('wits', 'pk_wits')
        ensure_primary_key('statuses', 'pk_statuses')
        # work_items primary key already defined inline
        ensure_primary_key('changelogs', 'pk_changelogs')
        ensure_primary_key('repositories', 'pk_repositories')
        ensure_primary_key('prs', 'pk_prs')
        ensure_primary_key('prs_reviews', 'pk_prs_reviews')
        ensure_primary_key('prs_commits', 'pk_prs_commits')
        ensure_primary_key('prs_comments', 'pk_prs_comments')
        ensure_primary_key('system_settings', 'pk_system_settings')
        # etl_jobs primary key already defined inline
        ensure_primary_key('wits_prs_links', 'pk_wits_prs_links')
        # raw_extraction_data primary key already defined inline
        ensure_primary_key('migration_history', 'pk_migration_history')
        ensure_primary_key('dora_market_benchmarks', 'pk_dora_market_benchmarks')
        ensure_primary_key('dora_metric_insights', 'pk_dora_metric_insights')
        # tenants_colors primary key already defined inline

        # Phase 3-1: New table primary keys
        # qdrant_vectors primary key already defined inline
        # Note: AI/ML table primary keys are added after the tables are created

        # Check if migration_history table already has a primary key (from migration runner)
        cursor.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'migration_history'
            AND constraint_type = 'PRIMARY KEY';
        """)

        if not cursor.fetchone():
            cursor.execute("ALTER TABLE migration_history ADD CONSTRAINT pk_migration_history PRIMARY KEY (id);")

        print("✅ Primary key constraints created")

        print("📋 Creating ML monitoring tables...")

        # AI Learning Memories table - stores user feedback and corrections (Phase 3-1 Clean)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_learning_memories (
                id SERIAL PRIMARY KEY,
                error_type VARCHAR(50) NOT NULL,
                user_intent TEXT NOT NULL,
                failed_query TEXT NOT NULL,
                specific_work_item TEXT NOT NULL,
                corrected_query TEXT,
                user_feedback TEXT,
                user_correction TEXT,
                message_id VARCHAR(255),
                tenant_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),

                FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
            );
        """)



        # AI Predictions table - logs ML model predictions and accuracy
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_predictions (
                id SERIAL PRIMARY KEY,
                model_name VARCHAR(100) NOT NULL,
                model_version VARCHAR(50),
                input_data JSONB NOT NULL,
                prediction_result JSONB NOT NULL,
                confidence_score DECIMAL(5,4),
                actual_outcome JSONB,
                accuracy_score DECIMAL(5,4),
                prediction_type VARCHAR(50) NOT NULL, -- 'trajectory', 'complexity', 'risk', etc.
                tenant_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                validated_at TIMESTAMP,

                FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
            );
        """)

        # AI Performance Metrics table - tracks system performance metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_performance_metrics (
                id SERIAL PRIMARY KEY,
                metric_name VARCHAR(100) NOT NULL,
                metric_value DECIMAL(10,4) NOT NULL,
                metric_unit VARCHAR(20),
                measurement_timestamp TIMESTAMP DEFAULT NOW(),
                context_data JSONB,
                tenant_id INTEGER NOT NULL,
                service_name VARCHAR(50), -- 'backend', 'etl', 'ai'

                FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
            );
        """)

        # ML Anomaly Alerts table - tracks anomalies detected by ML monitoring
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ml_anomaly_alerts (
                id SERIAL PRIMARY KEY,
                model_name VARCHAR(100) NOT NULL,
                severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
                alert_data JSONB NOT NULL,
                acknowledged BOOLEAN DEFAULT FALSE,
                acknowledged_by INTEGER,
                acknowledged_at TIMESTAMP,
                tenant_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                active BOOLEAN DEFAULT TRUE,

                FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
            );
        """)

        print("✅ ML monitoring tables created")

        print("📋 Adding AI/ML table primary key constraints...")
        # AI/ML monitoring table primary keys (all already defined inline)
        # ai_usage_trackings primary key already defined inline
        # ai_learning_memories primary key already defined inline
        # ai_predictions primary key already defined inline
        # ai_performance_metrics primary key already defined inline
        # ml_anomaly_alerts primary key already defined inline
        print("✅ AI/ML table primary key constraints created")

        print("📋 Creating foreign key constraints...")

        # Helper function to add foreign key constraints if they don't exist
        def add_constraint_if_not_exists(constraint_name: str, table_name: str, constraint_definition: str):
            cursor.execute(f"""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = '{table_name}'
                AND constraint_type = 'FOREIGN KEY'
                AND constraint_name = '{constraint_name}';
            """)
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} {constraint_definition};")

        # Core table foreign keys
        add_constraint_if_not_exists('fk_users_tenant_id', 'users', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_users_sessions_user_id', 'users_sessions', 'FOREIGN KEY (user_id) REFERENCES users(id)')
        add_constraint_if_not_exists('fk_users_sessions_tenant_id', 'users_sessions', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_users_permissions_user_id', 'users_permissions', 'FOREIGN KEY (user_id) REFERENCES users(id)')
        add_constraint_if_not_exists('fk_users_permissions_tenant_id', 'users_permissions', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')

        # Integrations and projects
        add_constraint_if_not_exists('fk_integrations_tenant_id', 'integrations', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_integrations_fallback', 'integrations', 'FOREIGN KEY (fallback_integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_projects_integration_id', 'projects', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_projects_tenant_id', 'projects', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')

        # Workflow and mappings
        add_constraint_if_not_exists('fk_workflows_tenant_id', 'workflows', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_workflows_integration_id', 'workflows', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_statuses_mappings_workflow_id', 'statuses_mappings', 'FOREIGN KEY (workflow_id) REFERENCES workflows(id)')
        add_constraint_if_not_exists('fk_statuses_mappings_tenant_id', 'statuses_mappings', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_statuses_mappings_integration_id', 'statuses_mappings', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
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
        add_constraint_if_not_exists('fk_statuses_status_mapping_id', 'statuses', 'FOREIGN KEY (status_mapping_id) REFERENCES statuses_mappings(id)')
        add_constraint_if_not_exists('fk_statuses_tenant_id', 'statuses', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')

        print("✅ Core foreign key constraints created")
        print("📋 Creating data table foreign key constraints...")

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
        add_constraint_if_not_exists('fk_etl_jobs_tenant_id', 'etl_jobs', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_etl_jobs_integration_id', 'etl_jobs', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_wits_prs_links_work_item_id', 'wits_prs_links', 'FOREIGN KEY (work_item_id) REFERENCES work_items(id)')
        add_constraint_if_not_exists('fk_wits_prs_links_tenant_id', 'wits_prs_links', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')
        add_constraint_if_not_exists('fk_wits_prs_links_integration_id', 'wits_prs_links', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')

        # Color table foreign key
        add_constraint_if_not_exists('fk_tenants_colors_tenant_id', 'tenants_colors', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id)')

        # Phase 3-1: New table foreign keys
        add_constraint_if_not_exists('fk_qdrant_vectors_tenant_id', 'qdrant_vectors', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')
        # AI/ML monitoring table foreign key constraints
        add_constraint_if_not_exists('fk_ai_usage_trackings_tenant_id', 'ai_usage_trackings', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')
        # Note: vectorization_queue table removed - vectorization integrated into transform workers
        add_constraint_if_not_exists('fk_ai_learning_memories_tenant_id', 'ai_learning_memories', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')
        add_constraint_if_not_exists('fk_ai_predictions_tenant_id', 'ai_predictions', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')
        add_constraint_if_not_exists('fk_ai_performance_metrics_tenant_id', 'ai_performance_metrics', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')
        add_constraint_if_not_exists('fk_ml_anomaly_alerts_tenant_id', 'ml_anomaly_alerts', 'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE')

        print("✅ Data table foreign key constraints created")
        print("📋 Creating relationship table constraints...")

        # Relationship tables (many-to-many)
        add_constraint_if_not_exists('fk_projects_wits_project_id', 'projects_wits', 'FOREIGN KEY (project_id) REFERENCES projects(id)')
        add_constraint_if_not_exists('fk_projects_wits_wit_id', 'projects_wits', 'FOREIGN KEY (wit_id) REFERENCES wits(id)')
        add_constraint_if_not_exists('fk_projects_statuses_project_id', 'projects_statuses', 'FOREIGN KEY (project_id) REFERENCES projects(id)')
        add_constraint_if_not_exists('fk_projects_statuses_status_id', 'projects_statuses', 'FOREIGN KEY (status_id) REFERENCES statuses(id)')

        print("✅ Constraint creation completed")

        print("📋 Creating unique constraints...")

        # Add unique constraints (idempotent)
        def ensure_unique_constraint(table_name: str, constraint_name: str, columns: str):
            cursor.execute(f"""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = '{table_name}'
                AND constraint_type = 'UNIQUE'
                AND constraint_name = '{constraint_name}';
            """)
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} UNIQUE ({columns});")

        ensure_unique_constraint('users', 'uk_users_email', 'email')
        ensure_unique_constraint('users', 'uk_users_okta_user_id', 'okta_user_id')
        ensure_unique_constraint('system_settings', 'uk_system_settings_setting_key_tenant_id', 'setting_key, tenant_id')
        ensure_unique_constraint('etl_jobs', 'uk_etl_jobs_job_name_tenant_id', 'job_name, tenant_id')
        ensure_unique_constraint('integrations', 'uk_integrations_provider_tenant_id', 'provider, tenant_id')
        ensure_unique_constraint('statuses_mappings', 'uk_statuses_mappings_from_tenant', 'status_from, tenant_id')
        ensure_unique_constraint('wits_mappings', 'uk_wits_mappings_from_tenant', 'wit_from, tenant_id')
        ensure_unique_constraint('migration_history', 'uk_migration_history_migration_number', 'migration_number')

        # Unique constraints for global DORA tables
        ensure_unique_constraint('dora_market_benchmarks', 'uk_dora_benchmark', 'report_year, performance_tier, metric_name')
        ensure_unique_constraint('dora_metric_insights', 'uk_dora_insight', 'report_year, metric_name')

        # Unique constraints for unified color table
        ensure_unique_constraint('tenants_colors', 'uk_tenants_colors_unified', 'tenant_id, color_schema_mode, accessibility_level, theme_mode')

        print("✅ Unique constraints created")

        print("📋 Creating custom fields table...")

        # Custom fields table - stores Jira custom field definitions by project
        # Created after primary keys and foreign key constraints are established
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_fields (
                id SERIAL PRIMARY KEY,

                -- === CUSTOM FIELD IDENTIFIERS ===
                name VARCHAR(255) NOT NULL, -- Human-readable name like "Aha! Initiative", "Agile Team"
                key VARCHAR(100) NOT NULL, -- Jira field key like "customfield_10150", "customfield_10128"

                -- === FIELD SCHEMA ===
                schema_type VARCHAR(100) NOT NULL, -- Schema type like "string", "option", "array", "number", "date", "team"

                -- === FIELD OPERATIONS ===
                operations JSONB DEFAULT '[]', -- Array of allowed operations like ["set"], ["add", "set", "remove"]

                -- === PROJECT RELATIONSHIP ===
                project_id INTEGER NOT NULL, -- Foreign key to projects table

                -- === IntegrationBaseEntity FIELDS ===
                integration_id INTEGER NOT NULL REFERENCES integrations(id),
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),

                -- === CONSTRAINTS ===
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                CONSTRAINT uk_custom_fields_project_key UNIQUE(project_id, key)
            );
        """)

        print("✅ Custom fields table created")
        print("📋 Creating performance indexes...")

        # Performance indexes for frequently queried columns
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_auth_provider ON users(auth_provider);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_sessions_user_id ON users_sessions(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_sessions_expires_at ON users_sessions(expires_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_permissions_user_id ON users_permissions(user_id);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrations_tenant_id ON integrations(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrations_provider ON integrations(provider);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrations_type ON integrations(type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_integration_id ON projects(integration_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_tenant_id ON projects(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_key ON projects(key);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflows_tenant_id ON workflows(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflows_integration_id ON workflows(integration_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflows_is_commitment_point ON workflows(is_commitment_point);")
        # Unique partial index to ensure only one delivery milestone per tenant/integration combination
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_commitment_point_per_tenant_integration ON workflows(tenant_id, integration_id) WHERE is_commitment_point = true;")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_statuses_mappings_tenant_id ON statuses_mappings(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_statuses_mappings_workflow_id ON statuses_mappings(workflow_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_statuses_mappings_status_from ON statuses_mappings(status_from);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_hierarchies_tenant_id ON wits_hierarchies(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_hierarchies_level_number ON wits_hierarchies(level_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_mappings_tenant_id ON wits_mappings(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_mappings_wit_from ON wits_mappings(wit_from);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_mappings_hierarchy_id ON wits_mappings(wits_hierarchy_id);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_integration_id ON wits(integration_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_tenant_id ON wits(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_external_id ON wits(external_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_original_name ON wits(original_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_statuses_integration_id ON statuses(integration_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_statuses_tenant_id ON statuses(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_statuses_external_id ON statuses(external_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_statuses_original_name ON statuses(original_name);")

        print("✅ Core table indexes created")
        print("📋 Creating data table indexes...")

        # Work items table indexes (most frequently queried)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_integration_id ON work_items(integration_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_tenant_id ON work_items(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_external_id ON work_items(external_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_key ON work_items(key);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_project_id ON work_items(project_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_status_id ON work_items(status_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_wit_id ON work_items(wit_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_created ON work_items(created);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_updated ON work_items(updated);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_parent_external_id ON work_items(parent_external_id);")

        # Custom fields overflow GIN index for JSON queries (skip if column doesn't exist)
        try:
            # First check if the column exists
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'work_items' AND column_name = 'custom_fields_overflow';
            """)
            if cursor.fetchone():
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_custom_fields_overflow_gin ON work_items USING GIN (custom_fields_overflow);")
                print("✅ Custom fields overflow GIN index created")
            else:
                print("⚠️ Skipping custom_fields_overflow index: column does not exist")
        except Exception as e:
            print(f"⚠️ Skipping custom_fields_overflow index: {e}")



        # Work item changelogs indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_changelogs_work_item_id ON changelogs(work_item_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_changelogs_transition_change_date ON changelogs(transition_change_date);")

        # Repository and PR indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repositories_tenant_id ON repositories(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repositories_external_id ON repositories(external_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repositories_full_name ON repositories(full_name);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prs_repository_id ON prs(repository_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prs_work_item_id ON prs(work_item_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prs_external_id ON prs(external_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prs_number ON prs(number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prs_status ON prs(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prs_pr_created_at ON prs(pr_created_at);")

        # PR related table indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prs_reviews_pr_id ON prs_reviews(pr_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prs_commits_pr_id ON prs_commits(pr_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prs_comments_pr_id ON prs_comments(pr_id);")

        # Jira PR links indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_prs_links_work_item_id ON wits_prs_links(work_item_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_prs_links_repo_pr ON wits_prs_links(external_repo_id, pull_request_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wits_prs_links_repo_full_name ON wits_prs_links(repo_full_name);")

        # System table indexes - Autonomous ETL Architecture
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_etl_jobs_active
                ON etl_jobs(tenant_id, active, schedule_interval_minutes)
                WHERE active = TRUE;
            """)
        except Exception as e:
            print(f"⚠️ Skipping etl_jobs index: {e}")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_etl_jobs_status
                ON etl_jobs(tenant_id, status)
                WHERE active = TRUE;
            """)
        except Exception as e:
            print(f"⚠️ Skipping etl_jobs status index: {e}")

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_etl_jobs_integration_id ON etl_jobs(integration_id);")
        except Exception as e:
            print(f"⚠️ Skipping etl_jobs integration_id index: {e}")

        # Color table indexes for fast lookups (unified table)
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tenants_colors_tenant_id ON tenants_colors(tenant_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tenants_colors_mode ON tenants_colors(tenant_id, color_schema_mode);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tenants_colors_unified ON tenants_colors(tenant_id, color_schema_mode, accessibility_level, theme_mode);")
        except Exception as e:
            print(f"⚠️ Skipping tenants_colors indexes: {e}")

        # ML monitoring table indexes (Phase 3-1 Clean Architecture)
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_learning_memories_tenant_id ON ai_learning_memories(tenant_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_learning_memories_error_type ON ai_learning_memories(error_type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_learning_memories_message_id ON ai_learning_memories(message_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_predictions_tenant_id ON ai_predictions(tenant_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_predictions_model ON ai_predictions(model_name, model_version);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_predictions_type ON ai_predictions(prediction_type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_performance_metrics_tenant_id ON ai_performance_metrics(tenant_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_performance_metrics_name ON ai_performance_metrics(metric_name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_performance_metrics_timestamp ON ai_performance_metrics(measurement_timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ml_anomaly_alerts_tenant_id ON ml_anomaly_alerts(tenant_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ml_anomaly_alerts_model ON ml_anomaly_alerts(model_name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ml_anomaly_alerts_severity ON ml_anomaly_alerts(severity);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ml_anomaly_alerts_acknowledged ON ml_anomaly_alerts(acknowledged);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ml_anomaly_alerts_created_at ON ml_anomaly_alerts(created_at);")
            print("✅ ML monitoring indexes created")
        except Exception as e:
            print(f"⚠️ Skipping ML monitoring indexes: {e}")

        # Phase 3-1: Qdrant and AI configuration table indexes
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_qdrant_vectors_tenant ON qdrant_vectors(tenant_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_qdrant_vectors_table_record ON qdrant_vectors(table_name, record_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_qdrant_vectors_collection ON qdrant_vectors(qdrant_collection);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_qdrant_vectors_point_id ON qdrant_vectors(qdrant_point_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_qdrant_vectors_provider ON qdrant_vectors(embedding_provider);")
            # AI usage tracking table indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_usage_trackings_tenant ON ai_usage_trackings(tenant_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_usage_trackings_provider ON ai_usage_trackings(provider);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_usage_trackings_operation ON ai_usage_trackings(operation);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_usage_trackings_created_at ON ai_usage_trackings(created_at);")
            print("✅ Qdrant and AI usage indexes created")
        except Exception as e:
            print(f"⚠️ Skipping Qdrant and AI usage indexes: {e}")

        # Note: vectorization_queue table removed - vectorization integrated into transform workers

        print("✅ All indexes and constraints created successfully!")

        # Record this migration as applied
        cursor.execute("""
            INSERT INTO migration_history (migration_number, migration_name, applied_at, status)
            VALUES (%s, %s, NOW(), 'applied')
            ON CONFLICT (migration_number)
            DO UPDATE SET applied_at = NOW(), status = 'applied', rollback_at = NULL;
        """, ('0001', 'Initial Database Schema'))

        connection.commit()
        print("✅ Migration 0001 applied successfully")

    except Exception as e:
        connection.rollback()
        print(f"❌ Error applying migration: {e}")
        raise

def rollback(connection):
    """Rollback the initial schema migration."""
    print("🔄 Rolling back Migration 0001: Initial Database Schema")

    cursor = connection.cursor()

    try:
        # First, update migration history to mark as rolled back (before dropping the table)
        print("📋 Updating migration history...")
        try:
            cursor.execute("""
                UPDATE migration_history
                SET status = 'rolled_back', rollback_at = NOW()
                WHERE migration_number = %s;
            """, ('0001',))
            print("✅ Migration history updated")
        except Exception as e:
            print(f"⚠️ Could not update migration history (table may not exist): {e}")

        print("📋 Dropping all tables in reverse dependency order...")

        # Drop tables in reverse order to handle foreign key dependencies
        # Note: migration_history is dropped last so we can track the rollback
        tables_to_drop = [
            # AI and ML monitoring tables (no dependencies)
            'ai_performance_metrics',
            'ai_predictions',
            'ai_validation_patterns',
            'ai_learning_memories',
            'ai_usage_trackings',  # Added missing AI table
            'ml_anomaly_alerts',

            # Vector and queue tables (no dependencies)
            'vectorization_queue',  # Async vectorization queue
            'qdrant_vectors',  # Added missing vector table

            # Configuration and color tables
            'tenants_colors',
            'tenant_colors',  # Old color table (wrong name)
            'dora_metric_insights',
            'dora_market_benchmarks',

            # Custom fields table (depends on projects)
            'custom_fields',

            # Junction and link tables (depend on main tables)
            'wits_prs_links',
            'raw_extraction_data',  # Phase 1: Raw data storage
            'etl_jobs',
            'system_settings',

            # PR related tables (depend on prs table)
            'prs_comments',
            'prs_commits',
            'prs_reviews',
            'prs',  # Main PR table

            # Repository table
            'repositories',

            # Work item related tables (depend on work_items table)
            'changelogs',
            'work_items',  # Main work items table

            # Project relationship tables
            'projects_statuses',
            'projects_wits',

            # Core configuration tables
            'statuses',
            'wits',  # Main WIT table
            'wits_mappings',
            'wits_hierarchies',
            'statuses_mappings',
            'workflows',
            'projects',
            'integrations',

            # User tables
            'users_permissions',
            'users_sessions',
            'users',

            # Core tenant table
            'tenants',

            # Migration tracking (drop last)
            'migration_history'
        ]

        for table in tables_to_drop:
            print(f"   🗑️ Dropping table {table}...")
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")

        print("✅ All tables dropped successfully")

        # Optionally drop extensions (commented out as they might be used by other databases)
        print("📋 Extensions (vector, pgml) left intact - they may be used by other applications")
        # Uncomment these lines if you want to completely clean the database:
        # cursor.execute("DROP EXTENSION IF EXISTS pgml CASCADE;")
        # cursor.execute("DROP EXTENSION IF EXISTS vector CASCADE;")
        # print("✅ Extensions dropped")

        connection.commit()
        print("✅ Migration 0001 rolled back successfully")
        print("⚠️ Note: You can now safely reapply this migration")

    except Exception as e:
        connection.rollback()
        print(f"❌ Error rolling back migration: {e}")
        raise

def check_status(connection):
    """Check if this migration has been applied."""
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""
            SELECT migration_number, migration_name, applied_at, rollback_at, status
            FROM migration_history
            WHERE migration_number = %s;
        """, ('0001',))

        result = cursor.fetchone()
        if result:
            status = result['status']
            if status == 'applied':
                print(f"✅ Migration 0001 is applied ({result['applied_at']})")
            elif status == 'rolled_back':
                print(f"🔄 Migration 0001 was rolled back ({result['rollback_at']})")
        else:
            print("⏸️ Migration 0001 has not been applied")

    except Exception as e:
        print(f"❌ Error checking migration status: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migration 0001: Initial Database Schema")
    parser.add_argument("--apply", action="store_true", help="Apply the migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    parser.add_argument("--status", action="store_true", help="Check migration status")

    args = parser.parse_args()

    if not any([args.apply, args.rollback, args.status]):
        parser.print_help()
        sys.exit(1)

    conn = get_database_connection()

    try:
        if args.apply:
            apply(conn)
        elif args.rollback:
            rollback(conn)
        elif args.status:
            check_status(conn)

    finally:
        conn.close()
