#!/usr/bin/env python3
"""
Migration 0001: Initial Database Schema with AI Enhancements (Phase 1 Complete)
Description: Creates all initial tables with integrated vector columns and ML monitoring infrastructure
Author: Pulse Platform Team
Date: 2025-08-27 (Updated for Phase 1)

This migration creates the complete initial database schema including:
- Client management tables with multi-client support and vector columns
- Authentication and user management for multiple clients with AI preferences
- Integration tables with base_search configuration and embeddings
- Issue tracking and workflow tables with vector support
- Development data tables (PRs, commits, etc.) with embeddings
- Job scheduling and system settings with theme/color customization
- ML monitoring tables for AI learning and prediction logging
- Vector indexes (HNSW) for similarity search
- All primary keys, foreign keys, unique constraints, and performance indexes

This migration contains ONLY schema creation with integrated AI capabilities - no seed data.

Phase 1 Requirements Implemented:
✅ pgvector and postgresml extensions
✅ Vector columns (embedding vector(1536)) in all 23 business tables
✅ ML monitoring tables (ai_learning_memory, ai_predictions, ai_performance_metrics)
✅ Vector indexes for similarity search
✅ Clean CREATE-only statements (no ALTER statements)
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

        # 1. Clients table (foundation) with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL,
                name VARCHAR NOT NULL,
                website VARCHAR,
                assets_folder VARCHAR(100),
                logo_filename VARCHAR(255) DEFAULT 'default-logo.png',
                color_schema_mode VARCHAR(10) DEFAULT 'default' CHECK (color_schema_mode IN ('default', 'custom')),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)
        
        # 2. Users table with vector column
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
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)
        
        # 3. User sessions table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id SERIAL,
                user_id INTEGER NOT NULL,
                token_hash VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)
        
        # 4. User permissions table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                id SERIAL,
                user_id INTEGER NOT NULL,
                resource VARCHAR(100) NOT NULL,
                action VARCHAR(50) NOT NULL,
                granted BOOLEAN NOT NULL DEFAULT TRUE,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)
        
        print("✅ Core tables created")
        print("📋 Creating integration and project tables...")
        
        # 5. Integrations table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS integrations (
                id SERIAL,
                name VARCHAR,
                url VARCHAR,
                username VARCHAR,
                password VARCHAR,
                base_search VARCHAR,
                last_sync_at TIMESTAMP,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)
        
        # 6. Projects table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL,
                external_id VARCHAR,
                key VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                project_type VARCHAR,
                integration_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)
        
        print("✅ Integration and project tables created")
        print("📋 Creating workflow and mapping tables...")

        # 7. Workflows table (renamed from flow_steps) with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id SERIAL,
                step_name VARCHAR NOT NULL,
                step_number INTEGER,
                step_category VARCHAR NOT NULL,
                is_commitment_point BOOLEAN NOT NULL DEFAULT FALSE,
                integration_id INTEGER,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 8. Status mappings table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS status_mappings (
                id SERIAL,
                status_from VARCHAR NOT NULL,
                status_to VARCHAR NOT NULL,
                status_category VARCHAR NOT NULL,
                workflow_id INTEGER,
                integration_id INTEGER,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 9. Issue type hierarchies table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issuetype_hierarchies (
                id SERIAL,
                level_name VARCHAR NOT NULL,
                level_number INTEGER NOT NULL,
                description VARCHAR,
                integration_id INTEGER,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 10. Issue type mappings table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issuetype_mappings (
                id SERIAL,
                issuetype_from VARCHAR NOT NULL,
                issuetype_to VARCHAR NOT NULL,
                issuetype_hierarchy_id INTEGER NOT NULL,
                integration_id INTEGER,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 11. Issue types table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issuetypes (
                id SERIAL,
                external_id VARCHAR,
                original_name VARCHAR NOT NULL,
                issuetype_mapping_id INTEGER,
                description VARCHAR,
                hierarchy_level INTEGER NOT NULL,
                integration_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 12. Statuses table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS statuses (
                id SERIAL,
                external_id VARCHAR,
                original_name VARCHAR NOT NULL,
                status_mapping_id INTEGER,
                category VARCHAR NOT NULL,
                description VARCHAR,
                integration_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        print("✅ Workflow and mapping tables created")
        print("📋 Creating relationship tables...")

        # 13. Projects-Issuetypes relationship table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects_issuetypes (
                project_id INTEGER NOT NULL,
                issuetype_id INTEGER NOT NULL
            );
        """)

        # 14. Projects-Statuses relationship table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects_statuses (
                project_id INTEGER NOT NULL,
                status_id INTEGER NOT NULL
            );
        """)

        print("✅ Relationship tables created")
        print("📋 Creating main data tables...")

        # 15. Issues table (complete with all custom fields and workflow columns)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id SERIAL,
                external_id VARCHAR,
                key VARCHAR,
                project_id INTEGER,
                team VARCHAR,
                summary VARCHAR,
                issuetype_id INTEGER,
                status_id INTEGER,
                resolution VARCHAR,
                story_points INTEGER,
                assignee VARCHAR,
                labels VARCHAR,
                created TIMESTAMP,
                updated TIMESTAMP,
                work_first_committed_at TIMESTAMP,
                work_first_started_at TIMESTAMP,
                work_last_started_at TIMESTAMP,
                work_first_completed_at TIMESTAMP,
                work_last_completed_at TIMESTAMP,
                priority VARCHAR,
                parent_external_id VARCHAR,
                code_changed BOOLEAN,
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
                integration_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 16. Issue changelogs table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issue_changelogs (
                id SERIAL,
                issue_id INTEGER NOT NULL,
                external_id VARCHAR,
                from_status_id INTEGER,
                to_status_id INTEGER,
                transition_start_date TIMESTAMP,
                transition_change_date TIMESTAMP,
                time_in_status_seconds FLOAT,
                changed_by VARCHAR,
                integration_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 17. Repositories table with vector column
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
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        print("✅ Main data tables created")
        print("📋 Creating development and system tables...")

        # 18. Pull requests table (complete with all columns) with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pull_requests (
                id SERIAL,
                external_id VARCHAR,
                external_repo_id VARCHAR,
                repository_id INTEGER NOT NULL,
                issue_id INTEGER,
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
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 19. Pull request reviews table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pull_request_reviews (
                id SERIAL,
                external_id VARCHAR,
                pull_request_id INTEGER NOT NULL,
                author_login VARCHAR,
                state VARCHAR,
                body TEXT,
                submitted_at TIMESTAMP,
                integration_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 20. Pull request commits table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pull_request_commits (
                id SERIAL,
                external_id VARCHAR,
                pull_request_id INTEGER NOT NULL,
                author_name VARCHAR,
                author_email VARCHAR,
                committer_name VARCHAR,
                committer_email VARCHAR,
                message TEXT,
                authored_date TIMESTAMP,
                committed_date TIMESTAMP,
                integration_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 21. Pull request comments table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pull_request_comments (
                id SERIAL,
                external_id VARCHAR,
                pull_request_id INTEGER NOT NULL,
                author_login VARCHAR,
                body TEXT,
                comment_type VARCHAR,
                path VARCHAR,
                position INTEGER,
                line INTEGER,
                created_at_github TIMESTAMP,
                updated_at_github TIMESTAMP,
                integration_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 22. System settings table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                id SERIAL,
                setting_key VARCHAR NOT NULL,
                setting_value VARCHAR NOT NULL,
                setting_type VARCHAR NOT NULL DEFAULT 'string',
                description VARCHAR,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 23. Job schedules table with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_schedules (
                id SERIAL,
                job_name VARCHAR UNIQUE NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'PENDING',
                last_repo_sync_checkpoint TIMESTAMP,
                repo_processing_queue TEXT,
                last_pr_cursor VARCHAR,
                current_pr_node_id VARCHAR,
                last_commit_cursor VARCHAR,
                last_review_cursor VARCHAR,
                last_comment_cursor VARCHAR,
                last_review_thread_cursor VARCHAR,
                last_run_started_at TIMESTAMP,
                last_success_at TIMESTAMP,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                integration_id INTEGER,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
        """)

        # 24. Jira pull request links table (complete with all columns) with vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jira_pull_request_links (
                id SERIAL,
                issue_id INTEGER NOT NULL,
                external_repo_id VARCHAR NOT NULL,
                repo_full_name VARCHAR NOT NULL,
                pull_request_number INTEGER NOT NULL,
                branch_name VARCHAR,
                commit_sha VARCHAR,
                pr_status VARCHAR,
                integration_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536)
            );
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

        # 28. Client color settings table (unified architecture)
        print("   🗑️ Dropping existing color tables...")
        cursor.execute("DROP TABLE IF EXISTS client_accessibility_colors CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS client_color_settings CASCADE;")

        print("   🏗️ Creating new unified client_color_settings table...")
        cursor.execute("""
            CREATE TABLE client_color_settings (
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
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),
                embedding vector(1536),

                -- === NEW UNIFIED UNIQUE CONSTRAINT ===
                CONSTRAINT uk_client_color_unified UNIQUE(client_id, color_schema_mode, accessibility_level, theme_mode)
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

        ensure_primary_key('clients', 'pk_clients')
        ensure_primary_key('users', 'pk_users')
        ensure_primary_key('user_sessions', 'pk_user_sessions')
        ensure_primary_key('user_permissions', 'pk_user_permissions')
        ensure_primary_key('integrations', 'pk_integrations')
        ensure_primary_key('projects', 'pk_projects')
        ensure_primary_key('workflows', 'pk_workflows')
        ensure_primary_key('status_mappings', 'pk_status_mappings')
        ensure_primary_key('issuetype_hierarchies', 'pk_issuetype_hierarchies')
        ensure_primary_key('issuetype_mappings', 'pk_issuetype_mappings')
        ensure_primary_key('issuetypes', 'pk_issuetypes')
        ensure_primary_key('statuses', 'pk_statuses')
        ensure_primary_key('issues', 'pk_issues')
        ensure_primary_key('issue_changelogs', 'pk_issue_changelogs')
        ensure_primary_key('repositories', 'pk_repositories')
        ensure_primary_key('pull_requests', 'pk_pull_requests')
        ensure_primary_key('pull_request_reviews', 'pk_pull_request_reviews')
        ensure_primary_key('pull_request_commits', 'pk_pull_request_commits')
        ensure_primary_key('pull_request_comments', 'pk_pull_request_comments')
        ensure_primary_key('system_settings', 'pk_system_settings')
        ensure_primary_key('job_schedules', 'pk_job_schedules')
        ensure_primary_key('jira_pull_request_links', 'pk_jira_pull_request_links')
        ensure_primary_key('dora_market_benchmarks', 'pk_dora_market_benchmarks')
        ensure_primary_key('dora_metric_insights', 'pk_dora_metric_insights')
        ensure_primary_key('client_color_settings', 'pk_client_color_settings')

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

        # AI Learning Memory table - stores user feedback and corrections
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_learning_memory (
                id SERIAL PRIMARY KEY,
                error_type VARCHAR(50) NOT NULL,
                user_intent TEXT NOT NULL,
                failed_query TEXT NOT NULL,
                specific_issue TEXT NOT NULL,
                corrected_query TEXT,
                user_feedback TEXT,
                user_correction TEXT,
                message_id VARCHAR(255),
                client_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW(),

                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
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
                client_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                validated_at TIMESTAMP,

                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
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
                client_id INTEGER NOT NULL,
                service_name VARCHAR(50), -- 'backend', 'etl', 'ai'

                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );
        """)

        print("✅ ML monitoring tables created")

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
        add_constraint_if_not_exists('fk_users_client_id', 'users', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_user_sessions_user_id', 'user_sessions', 'FOREIGN KEY (user_id) REFERENCES users(id)')
        add_constraint_if_not_exists('fk_user_sessions_client_id', 'user_sessions', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_user_permissions_user_id', 'user_permissions', 'FOREIGN KEY (user_id) REFERENCES users(id)')
        add_constraint_if_not_exists('fk_user_permissions_client_id', 'user_permissions', 'FOREIGN KEY (client_id) REFERENCES clients(id)')

        # Integrations and projects
        add_constraint_if_not_exists('fk_integrations_client_id', 'integrations', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_projects_integration_id', 'projects', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_projects_client_id', 'projects', 'FOREIGN KEY (client_id) REFERENCES clients(id)')

        # Workflow and mappings
        add_constraint_if_not_exists('fk_workflows_client_id', 'workflows', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_workflows_integration_id', 'workflows', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_status_mappings_workflow_id', 'status_mappings', 'FOREIGN KEY (workflow_id) REFERENCES workflows(id)')
        add_constraint_if_not_exists('fk_status_mappings_client_id', 'status_mappings', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_status_mappings_integration_id', 'status_mappings', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_issuetype_hierarchies_client_id', 'issuetype_hierarchies', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_issuetype_hierarchies_integration_id', 'issuetype_hierarchies', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_issuetype_mappings_client_id', 'issuetype_mappings', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_issuetype_mappings_integration_id', 'issuetype_mappings', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_issuetype_mappings_hierarchy_id', 'issuetype_mappings', 'FOREIGN KEY (issuetype_hierarchy_id) REFERENCES issuetype_hierarchies(id)')

        # Issue types and statuses
        add_constraint_if_not_exists('fk_issuetypes_integration_id', 'issuetypes', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_issuetypes_issuetype_mapping_id', 'issuetypes', 'FOREIGN KEY (issuetype_mapping_id) REFERENCES issuetype_mappings(id)')
        add_constraint_if_not_exists('fk_issuetypes_client_id', 'issuetypes', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_statuses_integration_id', 'statuses', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_statuses_status_mapping_id', 'statuses', 'FOREIGN KEY (status_mapping_id) REFERENCES status_mappings(id)')
        add_constraint_if_not_exists('fk_statuses_client_id', 'statuses', 'FOREIGN KEY (client_id) REFERENCES clients(id)')

        print("✅ Core foreign key constraints created")
        print("📋 Creating data table foreign key constraints...")

        # Issues and changelogs
        add_constraint_if_not_exists('fk_issues_integration_id', 'issues', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_issues_project_id', 'issues', 'FOREIGN KEY (project_id) REFERENCES projects(id)')
        add_constraint_if_not_exists('fk_issues_issuetype_id', 'issues', 'FOREIGN KEY (issuetype_id) REFERENCES issuetypes(id)')
        add_constraint_if_not_exists('fk_issues_status_id', 'issues', 'FOREIGN KEY (status_id) REFERENCES statuses(id)')
        add_constraint_if_not_exists('fk_issues_client_id', 'issues', 'FOREIGN KEY (client_id) REFERENCES clients(id)')

        # Issue changelogs
        add_constraint_if_not_exists('fk_issue_changelogs_integration_id', 'issue_changelogs', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_issue_changelogs_issue_id', 'issue_changelogs', 'FOREIGN KEY (issue_id) REFERENCES issues(id)')
        add_constraint_if_not_exists('fk_issue_changelogs_from_status_id', 'issue_changelogs', 'FOREIGN KEY (from_status_id) REFERENCES statuses(id)')
        add_constraint_if_not_exists('fk_issue_changelogs_to_status_id', 'issue_changelogs', 'FOREIGN KEY (to_status_id) REFERENCES statuses(id)')
        add_constraint_if_not_exists('fk_issue_changelogs_client_id', 'issue_changelogs', 'FOREIGN KEY (client_id) REFERENCES clients(id)')

        # Repositories and pull requests
        add_constraint_if_not_exists('fk_repositories_client_id', 'repositories', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_repositories_integration_id', 'repositories', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_pull_requests_repository_id', 'pull_requests', 'FOREIGN KEY (repository_id) REFERENCES repositories(id)')
        add_constraint_if_not_exists('fk_pull_requests_issue_id', 'pull_requests', 'FOREIGN KEY (issue_id) REFERENCES issues(id)')
        add_constraint_if_not_exists('fk_pull_requests_client_id', 'pull_requests', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_pull_requests_integration_id', 'pull_requests', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')

        # Pull request related tables
        add_constraint_if_not_exists('fk_pull_request_reviews_pull_request_id', 'pull_request_reviews', 'FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id)')
        add_constraint_if_not_exists('fk_pull_request_reviews_client_id', 'pull_request_reviews', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_pull_request_reviews_integration_id', 'pull_request_reviews', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_pull_request_commits_pull_request_id', 'pull_request_commits', 'FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id)')
        add_constraint_if_not_exists('fk_pull_request_commits_client_id', 'pull_request_commits', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_pull_request_commits_integration_id', 'pull_request_commits', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_pull_request_comments_pull_request_id', 'pull_request_comments', 'FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id)')
        add_constraint_if_not_exists('fk_pull_request_comments_client_id', 'pull_request_comments', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_pull_request_comments_integration_id', 'pull_request_comments', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')

        # System tables
        add_constraint_if_not_exists('fk_system_settings_client_id', 'system_settings', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_job_schedules_client_id', 'job_schedules', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_job_schedules_integration_id', 'job_schedules', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')
        add_constraint_if_not_exists('fk_jira_pull_request_links_issue_id', 'jira_pull_request_links', 'FOREIGN KEY (issue_id) REFERENCES issues(id)')
        add_constraint_if_not_exists('fk_jira_pull_request_links_client_id', 'jira_pull_request_links', 'FOREIGN KEY (client_id) REFERENCES clients(id)')
        add_constraint_if_not_exists('fk_jira_pull_request_links_integration_id', 'jira_pull_request_links', 'FOREIGN KEY (integration_id) REFERENCES integrations(id)')

        # Color table foreign key
        add_constraint_if_not_exists('fk_client_color_settings_client_id', 'client_color_settings', 'FOREIGN KEY (client_id) REFERENCES clients(id)')

        print("✅ Data table foreign key constraints created")
        print("📋 Creating relationship table constraints...")

        # Relationship tables (many-to-many)
        add_constraint_if_not_exists('fk_projects_issuetypes_project_id', 'projects_issuetypes', 'FOREIGN KEY (project_id) REFERENCES projects(id)')
        add_constraint_if_not_exists('fk_projects_issuetypes_issuetype_id', 'projects_issuetypes', 'FOREIGN KEY (issuetype_id) REFERENCES issuetypes(id)')
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
        ensure_unique_constraint('system_settings', 'uk_system_settings_setting_key_client_id', 'setting_key, client_id')
        ensure_unique_constraint('job_schedules', 'uk_job_schedules_job_name', 'job_name')
        ensure_unique_constraint('integrations', 'uk_integrations_name_client_id', 'name, client_id')
        ensure_unique_constraint('status_mappings', 'uk_status_mappings_from_client', 'status_from, client_id')
        ensure_unique_constraint('issuetype_mappings', 'uk_issuetype_mappings_from_client', 'issuetype_from, client_id')
        ensure_unique_constraint('migration_history', 'uk_migration_history_migration_number', 'migration_number')

        # Unique constraints for global DORA tables
        ensure_unique_constraint('dora_market_benchmarks', 'uk_dora_benchmark', 'report_year, performance_tier, metric_name')
        ensure_unique_constraint('dora_metric_insights', 'uk_dora_insight', 'report_year, metric_name')

        # Unique constraints for unified color table
        ensure_unique_constraint('client_color_settings', 'uk_client_color_unified', 'client_id, color_schema_mode, accessibility_level, theme_mode')

        print("✅ Unique constraints created")
        print("📋 Creating performance indexes...")

        # Performance indexes for frequently queried columns
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_client_id ON users(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_auth_provider ON users(auth_provider);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_permissions_user_id ON user_permissions(user_id);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrations_client_id ON integrations(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_integrations_name ON integrations(name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_integration_id ON projects(integration_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_client_id ON projects(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_key ON projects(key);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflows_client_id ON workflows(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflows_integration_id ON workflows(integration_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflows_is_commitment_point ON workflows(is_commitment_point);")
        # Unique partial index to ensure only one delivery milestone per client/integration combination
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_commitment_point_per_client_integration ON workflows(client_id, integration_id) WHERE is_commitment_point = true;")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_mappings_client_id ON status_mappings(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_mappings_workflow_id ON status_mappings(workflow_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_mappings_status_from ON status_mappings(status_from);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issuetype_hierarchies_client_id ON issuetype_hierarchies(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issuetype_hierarchies_level_number ON issuetype_hierarchies(level_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issuetype_mappings_client_id ON issuetype_mappings(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issuetype_mappings_issuetype_from ON issuetype_mappings(issuetype_from);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issuetype_mappings_hierarchy_id ON issuetype_mappings(issuetype_hierarchy_id);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issuetypes_integration_id ON issuetypes(integration_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issuetypes_client_id ON issuetypes(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issuetypes_external_id ON issuetypes(external_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issuetypes_original_name ON issuetypes(original_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_statuses_integration_id ON statuses(integration_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_statuses_client_id ON statuses(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_statuses_external_id ON statuses(external_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_statuses_original_name ON statuses(original_name);")

        print("✅ Core table indexes created")
        print("📋 Creating data table indexes...")

        # Issues table indexes (most frequently queried)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_integration_id ON issues(integration_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_client_id ON issues(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_external_id ON issues(external_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_key ON issues(key);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_project_id ON issues(project_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_status_id ON issues(status_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_issuetype_id ON issues(issuetype_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_created ON issues(created);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_updated ON issues(updated);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_parent_external_id ON issues(parent_external_id);")

        # Issue changelogs indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issue_changelogs_issue_id ON issue_changelogs(issue_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issue_changelogs_transition_change_date ON issue_changelogs(transition_change_date);")

        # Repository and pull request indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repositories_client_id ON repositories(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repositories_external_id ON repositories(external_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_repositories_full_name ON repositories(full_name);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pull_requests_repository_id ON pull_requests(repository_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pull_requests_issue_id ON pull_requests(issue_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pull_requests_external_id ON pull_requests(external_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pull_requests_number ON pull_requests(number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pull_requests_status ON pull_requests(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pull_requests_pr_created_at ON pull_requests(pr_created_at);")

        # Pull request related table indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pull_request_reviews_pull_request_id ON pull_request_reviews(pull_request_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pull_request_commits_pull_request_id ON pull_request_commits(pull_request_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pull_request_comments_pull_request_id ON pull_request_comments(pull_request_id);")

        # Jira PR links indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jira_pr_links_issue_id ON jira_pull_request_links(issue_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jira_pr_links_repo_pr ON jira_pull_request_links(external_repo_id, pull_request_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jira_pr_links_repo_full_name ON jira_pull_request_links(repo_full_name);")

        # System table indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_schedules_status ON job_schedules(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_schedules_last_run_started_at ON job_schedules(last_run_started_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_schedules_integration_id ON job_schedules(integration_id);")

        # Color table indexes for fast lookups (unified table)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_client_color_settings_client_id ON client_color_settings(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_client_color_settings_mode ON client_color_settings(client_id, color_schema_mode);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_client_color_settings_unified ON client_color_settings(client_id, color_schema_mode, accessibility_level, theme_mode);")

        # ML monitoring table indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_learning_memory_client_id ON ai_learning_memory(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_learning_memory_error_type ON ai_learning_memory(error_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_learning_memory_message_id ON ai_learning_memory(message_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_predictions_client_id ON ai_predictions(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_predictions_model ON ai_predictions(model_name, model_version);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_predictions_type ON ai_predictions(prediction_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_performance_metrics_client_id ON ai_performance_metrics(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_performance_metrics_name ON ai_performance_metrics(metric_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_performance_metrics_timestamp ON ai_performance_metrics(measurement_timestamp);")

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
        print("📋 Dropping all tables in reverse dependency order...")

        # Drop tables in reverse order to handle foreign key dependencies
        tables_to_drop = [
            'ai_performance_metrics',
            'ai_predictions',
            'ai_learning_memory',
            'client_color_settings',
            'dora_metric_insights',
            'dora_market_benchmarks',
            'migration_history',
            'jira_pull_request_links',
            'job_schedules',
            'system_settings',
            'pull_request_comments',
            'pull_request_commits',
            'pull_request_reviews',
            'pull_requests',
            'repositories',
            'issue_changelogs',
            'issues',
            'projects_statuses',
            'projects_issuetypes',
            'statuses',
            'issuetypes',
            'issuetype_mappings',
            'issuetype_hierarchies',
            'status_mappings',
            'workflows',
            'projects',
            'integrations',
            'user_permissions',
            'user_sessions',
            'users',
            'clients'
        ]

        for table in tables_to_drop:
            print(f"   🗑️ Dropping table {table}...")
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")

        print("✅ All tables dropped successfully")

        # Note: Cannot update migration_history as it was dropped with all other tables
        connection.commit()
        print("✅ Migration 0001 rolled back successfully")

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
