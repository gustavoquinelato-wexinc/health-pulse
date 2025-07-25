#!/usr/bin/env python3
"""
Migration: 001 - Initial Schema
Description: Creates all initial tables, relationships, and inserts seed data for the Pulse Platform
Author: Pulse Platform Team
Date: 2025-07-21

This migration creates the complete initial database schema including:
- Client management tables
- Authentication and user management
- Integration and project tables  
- Issue tracking and workflow tables
- Development data tables (PRs, commits, etc.)
- Job scheduling and system settings
- Initial seed data for workflow configuration
"""

import os
import sys
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Add the ETL service to the path to access database configuration
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'services', 'etl-service'))

def get_database_connection():
    """Get database connection using ETL service configuration."""
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
    """Apply the initial schema migration."""
    print("🚀 Applying Migration 001: Initial Schema")
    
    cursor = connection.cursor()
    
    try:
        # Start transaction
        print("📋 Creating core tables...")
        
        # 1. Clients table (foundation)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL,
                name VARCHAR NOT NULL,
                website VARCHAR,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # 2. Users table
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
                last_login_at TIMESTAMP,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # 3. User sessions table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # 4. User permissions table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        print("✅ Core tables created")
        print("📋 Creating integration and project tables...")
        
        # 5. Integrations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS integrations (
                id SERIAL,
                name VARCHAR,
                url VARCHAR,
                username VARCHAR,
                password VARCHAR,
                last_sync_at TIMESTAMP,
                client_id INTEGER NOT NULL,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # 6. Projects table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        print("✅ Integration and project tables created")
        print("📋 Creating workflow and mapping tables...")

        # 7. Workflows table (renamed from flow_steps)
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 8. Status mappings table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 9. Issue type hierarchies table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 10. Issue type mappings table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 11. Issue types table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 12. Statuses table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 16. Issue changelogs table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 17. Repositories table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        print("✅ Main data tables created")
        print("📋 Creating development and system tables...")

        # 18. Pull requests table (complete with all columns)
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 19. Pull request reviews table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 20. Pull request commits table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 21. Pull request comments table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 22. System settings table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 23. Job schedules table
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
                last_updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 24. Jira pull request links table (complete with all columns)
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
                last_updated_at TIMESTAMP DEFAULT NOW()
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

        print("✅ Development and system tables created")
        print("📋 Creating primary key constraints...")

        # Add explicit primary key constraints with proper names
        cursor.execute("ALTER TABLE clients ADD CONSTRAINT pk_clients PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE users ADD CONSTRAINT pk_users PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE user_sessions ADD CONSTRAINT pk_user_sessions PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE user_permissions ADD CONSTRAINT pk_user_permissions PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE integrations ADD CONSTRAINT pk_integrations PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE projects ADD CONSTRAINT pk_projects PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE workflows ADD CONSTRAINT pk_workflows PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE status_mappings ADD CONSTRAINT pk_status_mappings PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE issuetype_hierarchies ADD CONSTRAINT pk_issuetype_hierarchies PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE issuetype_mappings ADD CONSTRAINT pk_issuetype_mappings PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE issuetypes ADD CONSTRAINT pk_issuetypes PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE statuses ADD CONSTRAINT pk_statuses PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE issues ADD CONSTRAINT pk_issues PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE issue_changelogs ADD CONSTRAINT pk_issue_changelogs PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE repositories ADD CONSTRAINT pk_repositories PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE pull_requests ADD CONSTRAINT pk_pull_requests PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE pull_request_reviews ADD CONSTRAINT pk_pull_request_reviews PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE pull_request_commits ADD CONSTRAINT pk_pull_request_commits PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE pull_request_comments ADD CONSTRAINT pk_pull_request_comments PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE system_settings ADD CONSTRAINT pk_system_settings PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE job_schedules ADD CONSTRAINT pk_job_schedules PRIMARY KEY (id);")
        cursor.execute("ALTER TABLE jira_pull_request_links ADD CONSTRAINT pk_jira_pull_request_links PRIMARY KEY (id);")
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
        print("📋 Creating foreign key constraints...")

        # Add explicit foreign key constraints with proper names
        # Users and authentication
        cursor.execute("ALTER TABLE users ADD CONSTRAINT fk_users_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE user_sessions ADD CONSTRAINT fk_user_sessions_user_id FOREIGN KEY (user_id) REFERENCES users(id);")
        cursor.execute("ALTER TABLE user_sessions ADD CONSTRAINT fk_user_sessions_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE user_permissions ADD CONSTRAINT fk_user_permissions_user_id FOREIGN KEY (user_id) REFERENCES users(id);")
        cursor.execute("ALTER TABLE user_permissions ADD CONSTRAINT fk_user_permissions_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")

        # Integrations and projects
        cursor.execute("ALTER TABLE integrations ADD CONSTRAINT fk_integrations_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE projects ADD CONSTRAINT fk_projects_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE projects ADD CONSTRAINT fk_projects_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")

        # Workflow and mappings
        cursor.execute("ALTER TABLE workflows ADD CONSTRAINT fk_workflows_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE workflows ADD CONSTRAINT fk_workflows_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE status_mappings ADD CONSTRAINT fk_status_mappings_workflow_id FOREIGN KEY (workflow_id) REFERENCES workflows(id);")
        cursor.execute("ALTER TABLE status_mappings ADD CONSTRAINT fk_status_mappings_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE status_mappings ADD CONSTRAINT fk_status_mappings_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE issuetype_hierarchies ADD CONSTRAINT fk_issuetype_hierarchies_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE issuetype_hierarchies ADD CONSTRAINT fk_issuetype_hierarchies_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE issuetype_mappings ADD CONSTRAINT fk_issuetype_mappings_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE issuetype_mappings ADD CONSTRAINT fk_issuetype_mappings_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE issuetype_mappings ADD CONSTRAINT fk_issuetype_mappings_hierarchy_id FOREIGN KEY (issuetype_hierarchy_id) REFERENCES issuetype_hierarchies(id);")

        # Issue types and statuses
        cursor.execute("ALTER TABLE issuetypes ADD CONSTRAINT fk_issuetypes_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE issuetypes ADD CONSTRAINT fk_issuetypes_issuetype_mapping_id FOREIGN KEY (issuetype_mapping_id) REFERENCES issuetype_mappings(id);")
        cursor.execute("ALTER TABLE issuetypes ADD CONSTRAINT fk_issuetypes_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE statuses ADD CONSTRAINT fk_statuses_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE statuses ADD CONSTRAINT fk_statuses_status_mapping_id FOREIGN KEY (status_mapping_id) REFERENCES status_mappings(id);")
        cursor.execute("ALTER TABLE statuses ADD CONSTRAINT fk_statuses_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")

        print("✅ Core foreign key constraints created")
        print("📋 Creating data table foreign key constraints...")

        # Issues and changelogs
        cursor.execute("ALTER TABLE issues ADD CONSTRAINT fk_issues_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE issues ADD CONSTRAINT fk_issues_project_id FOREIGN KEY (project_id) REFERENCES projects(id);")
        cursor.execute("ALTER TABLE issues ADD CONSTRAINT fk_issues_issuetype_id FOREIGN KEY (issuetype_id) REFERENCES issuetypes(id);")
        cursor.execute("ALTER TABLE issues ADD CONSTRAINT fk_issues_status_id FOREIGN KEY (status_id) REFERENCES statuses(id);")
        cursor.execute("ALTER TABLE issues ADD CONSTRAINT fk_issues_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")

        cursor.execute("ALTER TABLE issue_changelogs ADD CONSTRAINT fk_issue_changelogs_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE issue_changelogs ADD CONSTRAINT fk_issue_changelogs_issue_id FOREIGN KEY (issue_id) REFERENCES issues(id);")
        cursor.execute("ALTER TABLE issue_changelogs ADD CONSTRAINT fk_issue_changelogs_from_status_id FOREIGN KEY (from_status_id) REFERENCES statuses(id);")
        cursor.execute("ALTER TABLE issue_changelogs ADD CONSTRAINT fk_issue_changelogs_to_status_id FOREIGN KEY (to_status_id) REFERENCES statuses(id);")
        cursor.execute("ALTER TABLE issue_changelogs ADD CONSTRAINT fk_issue_changelogs_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")

        # Repositories and pull requests
        cursor.execute("ALTER TABLE repositories ADD CONSTRAINT fk_repositories_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE repositories ADD CONSTRAINT fk_repositories_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE pull_requests ADD CONSTRAINT fk_pull_requests_repository_id FOREIGN KEY (repository_id) REFERENCES repositories(id);")
        cursor.execute("ALTER TABLE pull_requests ADD CONSTRAINT fk_pull_requests_issue_id FOREIGN KEY (issue_id) REFERENCES issues(id);")
        cursor.execute("ALTER TABLE pull_requests ADD CONSTRAINT fk_pull_requests_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE pull_requests ADD CONSTRAINT fk_pull_requests_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")

        # Pull request related tables
        cursor.execute("ALTER TABLE pull_request_reviews ADD CONSTRAINT fk_pull_request_reviews_pull_request_id FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id);")
        cursor.execute("ALTER TABLE pull_request_reviews ADD CONSTRAINT fk_pull_request_reviews_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE pull_request_reviews ADD CONSTRAINT fk_pull_request_reviews_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE pull_request_commits ADD CONSTRAINT fk_pull_request_commits_pull_request_id FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id);")
        cursor.execute("ALTER TABLE pull_request_commits ADD CONSTRAINT fk_pull_request_commits_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE pull_request_commits ADD CONSTRAINT fk_pull_request_commits_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE pull_request_comments ADD CONSTRAINT fk_pull_request_comments_pull_request_id FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id);")
        cursor.execute("ALTER TABLE pull_request_comments ADD CONSTRAINT fk_pull_request_comments_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE pull_request_comments ADD CONSTRAINT fk_pull_request_comments_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")

        # System tables
        cursor.execute("ALTER TABLE system_settings ADD CONSTRAINT fk_system_settings_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE job_schedules ADD CONSTRAINT fk_job_schedules_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE job_schedules ADD CONSTRAINT fk_job_schedules_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")
        cursor.execute("ALTER TABLE jira_pull_request_links ADD CONSTRAINT fk_jira_pull_request_links_issue_id FOREIGN KEY (issue_id) REFERENCES issues(id);")
        cursor.execute("ALTER TABLE jira_pull_request_links ADD CONSTRAINT fk_jira_pull_request_links_client_id FOREIGN KEY (client_id) REFERENCES clients(id);")
        cursor.execute("ALTER TABLE jira_pull_request_links ADD CONSTRAINT fk_jira_pull_request_links_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);")

        print("✅ Data table foreign key constraints created")
        print("📋 Creating relationship table constraints...")

        # Relationship tables (many-to-many)
        cursor.execute("ALTER TABLE projects_issuetypes ADD CONSTRAINT fk_projects_issuetypes_project_id FOREIGN KEY (project_id) REFERENCES projects(id);")
        cursor.execute("ALTER TABLE projects_issuetypes ADD CONSTRAINT fk_projects_issuetypes_issuetype_id FOREIGN KEY (issuetype_id) REFERENCES issuetypes(id);")
        cursor.execute("ALTER TABLE projects_statuses ADD CONSTRAINT fk_projects_statuses_project_id FOREIGN KEY (project_id) REFERENCES projects(id);")
        cursor.execute("ALTER TABLE projects_statuses ADD CONSTRAINT fk_projects_statuses_status_id FOREIGN KEY (status_id) REFERENCES statuses(id);")

        print("✅ Relationship table constraints created")
        print("📋 Creating unique constraints...")

        # Add unique constraints
        cursor.execute("ALTER TABLE users ADD CONSTRAINT uk_users_email UNIQUE (email);")
        cursor.execute("ALTER TABLE users ADD CONSTRAINT uk_users_okta_user_id UNIQUE (okta_user_id);")
        cursor.execute("ALTER TABLE system_settings ADD CONSTRAINT uk_system_settings_setting_key UNIQUE (setting_key);")
        cursor.execute("ALTER TABLE job_schedules ADD CONSTRAINT uk_job_schedules_job_name UNIQUE (job_name);")
        cursor.execute("ALTER TABLE integrations ADD CONSTRAINT uk_integrations_name_client_id UNIQUE (name, client_id);")
        cursor.execute("ALTER TABLE status_mappings ADD CONSTRAINT uk_status_mappings_from_client UNIQUE (status_from, client_id);")
        cursor.execute("ALTER TABLE issuetype_mappings ADD CONSTRAINT uk_issuetype_mappings_from_client UNIQUE (issuetype_from, client_id);")
        # Check if migration_history table already has unique constraint on migration_number
        cursor.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'migration_history'
            AND constraint_type = 'UNIQUE'
            AND constraint_name LIKE '%migration_number%';
        """)

        if not cursor.fetchone():
            cursor.execute("ALTER TABLE migration_history ADD CONSTRAINT uk_migration_history_migration_number UNIQUE (migration_number);")

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

        print("✅ All indexes and constraints created successfully!")
        print("📋 Inserting seed data...")

        # Insert default client (WEX)
        cursor.execute("""
            INSERT INTO clients (name, website, active, created_at, last_updated_at)
            VALUES ('WEX', 'https://www.wexinc.com', TRUE, NOW(), NOW())
            ON CONFLICT DO NOTHING;
        """)

        # Get the client ID for seed data
        cursor.execute("SELECT id FROM clients WHERE name = 'WEX' LIMIT 1;")
        client_result = cursor.fetchone()
        if not client_result:
            raise Exception("Failed to create or find WEX client")
        client_id = client_result['id']

        # Insert workflows (extracted from workflow configuration)
        # Note: integration_id will be set later after integrations are created
        workflows_data = [
            ("Backlog", 1, "To Do"),
            ("Refinement", 2, "To Do"),
            ("Ready to Work", 3, "To Do"),
            ("To Do", 4, "To Do"),
            ("In Progress", 5, "In Progress"),
            ("Ready for Story Testing", 6, "Waiting"),
            ("Story Testing", 7, "In Progress"),
            ("Ready for Acceptance", 8, "Waiting"),
            ("Acceptance Testing", 9, "In Progress"),
            ("Ready for Prod", 10, "Waiting"),
            ("Done", 11, "Done"),
            ("Discarded", None, "Discarded")  # No step number for Discarded
        ]

        workflow_ids = {}
        for step_name, step_number, category in workflows_data:
            # Set delivery milestone for "Done" step
            is_commitment_point = (step_name == "Done")

            cursor.execute("""
                INSERT INTO workflows (step_name, step_number, step_category, is_commitment_point, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT DO NOTHING
                RETURNING id;
            """, (step_name, step_number, category, is_commitment_point, client_id))

            result = cursor.fetchone()
            if result:
                workflow_ids[step_name] = result['id']
            else:
                # Get existing ID if conflict occurred
                cursor.execute("SELECT id FROM workflows WHERE step_name = %s AND client_id = %s;", (step_name, client_id))
                result = cursor.fetchone()
                if result:
                    workflow_ids[step_name] = result['id']

        # Insert status mappings (complete workflow configuration - EXACT COPY from reset_database.py)
        status_mappings_data = [
            #BACKLOG
            {"status_from": "Backlog", "status_to": "Backlog", "status_category": "To Do", "workflow": "Backlog"},
            {"status_from": "New", "status_to": "Backlog", "status_category": "To Do", "workflow": "Backlog"},
            {"status_from": "Open", "status_to": "Backlog", "status_category": "To Do", "workflow": "Backlog"},
            {"status_from": "Created", "status_to": "Backlog", "status_category": "To Do", "workflow": "Backlog"},

            #REFINEMENT
            {"status_from": "Analysis", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Design", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Prerefinement", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Ready to Refine", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Refinement", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Refining", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Tech Review", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Waiting for refinement", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "In Triage", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Pending Approval", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Discovery", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Composting", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Onboarding Templates", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Templates", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},
            {"status_from": "Template Approval Pending", "status_to": "Refinement", "status_category": "To Do", "workflow": "Refinement"},

            #READY TO WORK
            {"status_from": "Approved", "status_to": "Ready to Work", "status_category": "To Do", "workflow": "Ready to Work"},
            {"status_from": "Ready", "status_to": "Ready to Work", "status_category": "To Do", "workflow": "Ready to Work"},
            {"status_from": "Ready for Development", "status_to": "Ready to Work", "status_category": "To Do", "workflow": "Ready to Work"},
            {"status_from": "Ready to Development", "status_to": "Ready to Work", "status_category": "To Do", "workflow": "Ready to Work"},
            {"status_from": "Ready to Work", "status_to": "Ready to Work", "status_category": "To Do", "workflow": "Ready to Work"},
            {"status_from": "Refined", "status_to": "Ready to Work", "status_category": "To Do", "workflow": "Ready to Work"},
            {"status_from": "Proposed", "status_to": "Ready to Work", "status_category": "To Do", "workflow": "Ready to Work"},

            #TO DO
            {"status_from": "Committed", "status_to": "To Do", "status_category": "To Do", "workflow": "To Do"},
            {"status_from": "Planned", "status_to": "To Do", "status_category": "To Do", "workflow": "To Do"},
            {"status_from": "Selected for development", "status_to": "To Do", "status_category": "To Do", "workflow": "To Do"},
            {"status_from": "To Do", "status_to": "To Do", "status_category": "To Do", "workflow": "To Do"},

            #IN PROGRESS
            {"status_from": "Active", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Applied to TRN", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Blocked", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Building", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Code Review", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Codereview", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Coding", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Coding Done", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Deployed to Dev", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Development", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "In Development", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "In Progress", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "In Review", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Peer Review", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Pre-readiness", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Ready for Peer Review", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Ready to Dep to Dev", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Review", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Training", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Validated in TRN", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Waiting Partner", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "On Hold", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Pipeline Approval Pending", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},
            {"status_from": "Merging Branches", "status_to": "In Progress", "status_category": "In Progress", "workflow": "In Progress"},

            #READY FOR QA TESTING
            {"status_from": "Ready for QA", "status_to": "Ready for Story Testing", "status_category": "Waiting", "workflow": "Ready for Story Testing"},
            {"status_from": "Ready for QA build", "status_to": "Ready for Story Testing", "status_category": "Waiting", "workflow": "Ready for Story Testing"},
            {"status_from": "Ready for Test", "status_to": "Ready for Story Testing", "status_category": "Waiting", "workflow": "Ready for Story Testing"},
            {"status_from": "Ready for Testing", "status_to": "Ready for Story Testing", "status_category": "Waiting", "workflow": "Ready for Story Testing"},
            {"status_from": "Ready for Story Testing", "status_to": "Ready for Story Testing", "status_category": "Waiting", "workflow": "Ready for Story Testing"},
            {"status_from": "Deploying Demo", "status_to": "Ready for Story Testing", "status_category": "Waiting", "workflow": "Ready for Story Testing"},

            #IN QA TEST
            {"status_from": "Applied to QA", "status_to": "Story Testing", "status_category": "In Progress", "workflow": "Story Testing"},
            {"status_from": "In Test", "status_to": "Story Testing", "status_category": "In Progress", "workflow": "Story Testing"},
            {"status_from": "In Testing", "status_to": "Story Testing", "status_category": "In Progress", "workflow": "Story Testing"},
            {"status_from": "Promoted to QA", "status_to": "Story Testing", "status_category": "In Progress", "workflow": "Story Testing"},
            {"status_from": "QA", "status_to": "Story Testing", "status_category": "In Progress", "workflow": "Story Testing"},
            {"status_from": "QA in Progress", "status_to": "Story Testing", "status_category": "In Progress", "workflow": "Story Testing"},
            {"status_from": "Test", "status_to": "Story Testing", "status_category": "In Progress", "workflow": "Story Testing"},
            {"status_from": "Story Testing", "status_to": "Story Testing", "status_category": "In Progress", "workflow": "Story Testing"},
            {"status_from": "Testing", "status_to": "Story Testing", "status_category": "In Progress", "workflow": "Story Testing"},

            #READY FOR UAT TESTING
            {"status_from": "Ready for Uat", "status_to": "Ready for Acceptance", "status_category": "Waiting", "workflow": "Ready for Acceptance"},
            {"status_from": "Ready for Stage", "status_to": "Ready for Acceptance", "status_category": "Waiting", "workflow": "Ready for Acceptance"},
            {"status_from": "Validated in QA", "status_to": "Ready for Acceptance", "status_category": "Waiting", "workflow": "Ready for Acceptance"},
            {"status_from": "Ready for Demo", "status_to": "Ready for Acceptance", "status_category": "Waiting", "workflow": "Ready for Acceptance"},
            {"status_from": "Ready for Acceptance", "status_to": "Ready for Acceptance", "status_category": "Waiting", "workflow": "Ready for Acceptance"},

            #IN UAT TEST
            {"status_from": "Applied to STG", "status_to": "Acceptance Testing", "status_category": "In Progress", "workflow": "Acceptance Testing"},
            {"status_from": "Applied to UAT", "status_to": "Acceptance Testing", "status_category": "In Progress", "workflow": "Acceptance Testing"},
            {"status_from": "In Stage Testing", "status_to": "Acceptance Testing", "status_category": "In Progress", "workflow": "Acceptance Testing"},
            {"status_from": "Promoted to UAT", "status_to": "Acceptance Testing", "status_category": "In Progress", "workflow": "Acceptance Testing"},
            {"status_from": "Regression Testing", "status_to": "Acceptance Testing", "status_category": "In Progress", "workflow": "Acceptance Testing"},
            {"status_from": "Release Approval Pending", "status_to": "Acceptance Testing", "status_category": "In Progress", "workflow": "Acceptance Testing"},
            {"status_from": "UAT", "status_to": "Acceptance Testing", "status_category": "In Progress", "workflow": "Acceptance Testing"},
            {"status_from": "Acceptance Testing", "status_to": "Acceptance Testing", "status_category": "In Progress", "workflow": "Acceptance Testing"},
            {"status_from": "Pre Production Testing", "status_to": "Acceptance Testing", "status_category": "In Progress", "workflow": "Acceptance Testing"},
            {"status_from": "Final Checks", "status_to": "Acceptance Testing", "status_category": "In Progress", "workflow": "Acceptance Testing"},
            {"status_from": "Release Testing", "status_to": "Acceptance Testing", "status_category": "In Progress", "workflow": "Acceptance Testing"},

            #READY FOR PROD
            {"status_from": "Deploy", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Deployment", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Ready for prod", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Ready for prd", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Ready for production", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Ready for Release", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Ready to Dep to Prod", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Ready to Launch", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Release Pending", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Resolved", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Validated in STG", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Validated in UAT", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Deploying Database", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Deploying Applications", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},
            {"status_from": "Awaiting Deployment", "status_to": "Ready for Prod", "status_category": "Waiting", "workflow": "Ready for Prod"},

            #DONE
            {"status_from": "Applied to Prod", "status_to": "Done", "status_category": "Done", "workflow": "Done"},
            {"status_from": "Applied to Prod/TRN", "status_to": "Done", "status_category": "Done", "workflow": "Done"},
            {"status_from": "Closed", "status_to": "Done", "status_category": "Done", "workflow": "Done"},
            {"status_from": "Done", "status_to": "Done", "status_category": "Done", "workflow": "Done"},
            {"status_from": "Validated in Prod", "status_to": "Done", "status_category": "Done", "workflow": "Done"},
            {"status_from": "Released", "status_to": "Done", "status_category": "Done", "workflow": "Done"},
            {"status_from": "Deployed to Production", "status_to": "Done", "status_category": "Done", "workflow": "Done"},
            {"status_from": "Release Deployed", "status_to": "Done", "status_category": "Done", "workflow": "Done"},
            {"status_from": "Closure", "status_to": "Done", "status_category": "Done", "workflow": "Done"},

            #REMOVED
            {"status_from": "Cancelled", "status_to": "Discarded", "status_category": "Discarded", "workflow": "Discarded"},
            {"status_from": "Rejected", "status_to": "Discarded", "status_category": "Discarded", "workflow": "Discarded"},
            {"status_from": "Removed", "status_to": "Discarded", "status_category": "Discarded", "workflow": "Discarded"},
            {"status_from": "Withdrawn", "status_to": "Discarded", "status_category": "Discarded", "workflow": "Discarded"},
        ]

        for mapping in status_mappings_data:
            workflow_id = workflow_ids.get(mapping["workflow"])
            cursor.execute("""
                INSERT INTO status_mappings (status_from, status_to, status_category, workflow_id, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT (status_from, client_id) DO UPDATE SET
                    status_to = EXCLUDED.status_to,
                    status_category = EXCLUDED.status_category,
                    workflow_id = EXCLUDED.workflow_id,
                    last_updated_at = NOW();
            """, (mapping["status_from"], mapping["status_to"], mapping["status_category"], workflow_id, client_id))

        print("✅ Status mappings inserted")

        # Insert issuetype hierarchies
        issuetype_hierarchies_data = [
            {"level_name": "Capital Investment", "level_number": 4, "description": "Capital Investment / Theme"},
            {"level_name": "Product Objective", "level_number": 3, "description": "Product Objective / Initiative Name"},
            {"level_name": "Milestone", "level_number": 2, "description": "Milestone"},
            {"level_name": "Epic", "level_number": 1, "description": "Big chunk of work"},
            {"level_name": "Story", "level_number": 0, "description": "Small chunk of work"},
            {"level_name": "Sub-task", "level_number": -1, "description": "Internal Checklist Points"}
        ]

        for hierarchy in issuetype_hierarchies_data:
            cursor.execute("""
                INSERT INTO issuetype_hierarchies (level_name, level_number, description, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT DO NOTHING;
            """, (hierarchy["level_name"], hierarchy["level_number"], hierarchy["description"], client_id))

        print("✅ Issuetype hierarchies inserted")

        # Insert issuetype mappings
        issuetype_mappings_data = [
            #CAPITAL INVESTMENT
            {"issuetype_from": "Capital Investment", "issuetype_to": "Capital Investment", "hierarchy_level": 4},

            #PRODUCT OBJECTIVE
            {"issuetype_from": "Product Objective", "issuetype_to": "Product Objective", "hierarchy_level": 3},

            #MILESTONE
            {"issuetype_from": "Milestone", "issuetype_to": "Milestone", "hierarchy_level": 2},

            #EPIC
            {"issuetype_from": "Epic", "issuetype_to": "Epic", "hierarchy_level": 1},
            {"issuetype_from": "Feature", "issuetype_to": "Epic", "hierarchy_level": 1},

            #STORY
            {"issuetype_from": "User Story", "issuetype_to": "Story", "hierarchy_level": 0},
            {"issuetype_from": "Story", "issuetype_to": "Story", "hierarchy_level": 0},

            #TECH ENHANCEMENT
            {"issuetype_from": "Devops Story", "issuetype_to": "Tech Enhancement", "hierarchy_level": 0},
            {"issuetype_from": "Tech Debt", "issuetype_to": "Tech Enhancement", "hierarchy_level": 0},
            {"issuetype_from": "Performance", "issuetype_to": "Tech Enhancement", "hierarchy_level": 0},
            {"issuetype_from": "Security Remediation", "issuetype_to": "Tech Enhancement", "hierarchy_level": 0},
            {"issuetype_from": "Tech Enhancement", "issuetype_to": "Tech Enhancement", "hierarchy_level": 0},

            #TASK
            {"issuetype_from": "Task", "issuetype_to": "Task", "hierarchy_level": 0},
            {"issuetype_from": "UAT", "issuetype_to": "Task", "hierarchy_level": 0},
            {"issuetype_from": "Unparented Tasks", "issuetype_to": "Task", "hierarchy_level": 0},
            {"issuetype_from": "Shared Steps", "issuetype_to": "Task", "hierarchy_level": 0},
            {"issuetype_from": "Educational Services", "issuetype_to": "Task", "hierarchy_level": 0},
            {"issuetype_from": "Impediment", "issuetype_to": "Task", "hierarchy_level": 0},
            {"issuetype_from": "Requirement", "issuetype_to": "Task", "hierarchy_level": 0},
            {"issuetype_from": "Shared Parameter", "issuetype_to": "Task", "hierarchy_level": 0},

            #BUG (PROD)
            {"issuetype_from": "Bug", "issuetype_to": "Bug", "hierarchy_level": 0},

            #INCIDENT
            {"issuetype_from": "Issue", "issuetype_to": "Incident", "hierarchy_level": 0},
            {"issuetype_from": "Incident", "issuetype_to": "Incident", "hierarchy_level": 0},

            #SPIKE
            {"issuetype_from": "Spike", "issuetype_to": "Spike", "hierarchy_level": 0},

            #DEFECT (NON-PROD)
            {"issuetype_from": "Defect", "issuetype_to": "Defect", "hierarchy_level": -1},
            {"issuetype_from": "Sprint Issue", "issuetype_to": "Defect", "hierarchy_level": -1},
            {"issuetype_from": "Sub-task", "issuetype_to": "Sub-task", "hierarchy_level": -1},
            {"issuetype_from": "Approval", "issuetype_to": "Approval", "hierarchy_level": -1},
        ]

        for mapping in issuetype_mappings_data:
            # Get the hierarchy ID for this level
            cursor.execute("""
                SELECT id FROM issuetype_hierarchies
                WHERE level_number = %s AND client_id = %s
            """, (mapping["hierarchy_level"], client_id))
            hierarchy_result = cursor.fetchone()
            hierarchy_id = hierarchy_result['id'] if hierarchy_result else None

            if hierarchy_id:
                cursor.execute("""
                    INSERT INTO issuetype_mappings (issuetype_from, issuetype_to, issuetype_hierarchy_id, client_id, active, created_at, last_updated_at)
                    VALUES (%s, %s, %s, %s, TRUE, NOW(), NOW())
                    ON CONFLICT (issuetype_from, client_id) DO UPDATE SET
                        issuetype_to = EXCLUDED.issuetype_to,
                        issuetype_hierarchy_id = EXCLUDED.issuetype_hierarchy_id,
                        last_updated_at = NOW();
                """, (mapping["issuetype_from"], mapping["issuetype_to"], hierarchy_id, client_id))

        print("✅ Issuetype mappings inserted")

        # Insert default integrations (only if environment variables are available)
        print("📋 Creating default integrations...")

        # Try to read environment variables for integration configuration
        try:
            from app.core.config import Settings
            from app.core.config import AppConfig
            from app.core.utils import DateTimeHelper

            settings = Settings()
            integrations_created = 0

            # Create Jira integration (only if credentials are available)
            if settings.JIRA_URL and settings.JIRA_USERNAME and settings.JIRA_TOKEN:
                # Get encryption key
                key = AppConfig.load_key()
                encrypted_token = AppConfig.encrypt_token(settings.JIRA_TOKEN, key)

                # Set Jira last_sync_at to today at 12:00 PM Central Time
                today_noon = DateTimeHelper.now_central().replace(hour=12, minute=0, second=0, microsecond=0)

                cursor.execute("""
                    INSERT INTO integrations (name, url, username, password, last_sync_at, client_id, active, created_at, last_updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                    ON CONFLICT (name, client_id) DO NOTHING;
                """, ("JIRA", settings.JIRA_URL, settings.JIRA_USERNAME, encrypted_token, today_noon, client_id))
                integrations_created += 1
                print("   ✅ Jira integration created with encrypted credentials")
            else:
                print("   ⚠️  Jira integration skipped - missing environment variables (JIRA_URL, JIRA_USERNAME, JIRA_TOKEN)")

            # Create GitHub integration (only if token is available)
            if settings.GITHUB_TOKEN:
                key = AppConfig.load_key()
                encrypted_token = AppConfig.encrypt_token(settings.GITHUB_TOKEN, key)

                cursor.execute("""
                    INSERT INTO integrations (name, url, username, password, last_sync_at, client_id, active, created_at, last_updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                    ON CONFLICT (name, client_id) DO NOTHING;
                """, ("GITHUB", "https://api.github.com", None, encrypted_token, "2000-01-01 00:00:00", client_id))
                integrations_created += 1
                print("   ✅ GitHub integration created with encrypted credentials")
            else:
                print("   ⚠️  GitHub integration skipped - missing environment variable (GITHUB_TOKEN)")

            # Create Aha! integration (optional)
            if settings.AHA_TOKEN and settings.AHA_URL:
                key = AppConfig.load_key()
                encrypted_token = AppConfig.encrypt_token(settings.AHA_TOKEN, key)

                cursor.execute("""
                    INSERT INTO integrations (name, url, username, password, last_sync_at, client_id, active, created_at, last_updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                    ON CONFLICT (name, client_id) DO NOTHING;
                """, ("AHA!", settings.AHA_URL, None, encrypted_token, "2000-01-01 00:00:00", client_id))
                integrations_created += 1
                print("   ✅ Aha! integration created with encrypted credentials")
            else:
                print("   ⚠️  Aha! integration skipped - missing environment variables (AHA_TOKEN, AHA_URL)")

            # Create Azure DevOps integration (optional)
            if settings.AZDO_TOKEN and settings.AZDO_URL:
                key = AppConfig.load_key()
                encrypted_token = AppConfig.encrypt_token(settings.AZDO_TOKEN, key)

                cursor.execute("""
                    INSERT INTO integrations (name, url, username, password, last_sync_at, client_id, active, created_at, last_updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                    ON CONFLICT (name, client_id) DO NOTHING;
                """, ("AZURE DEVOPS", settings.AZDO_URL, None, encrypted_token, "2000-01-01 00:00:00", client_id))
                integrations_created += 1
                print("   ✅ Azure DevOps integration created with encrypted credentials")
            else:
                print("   ⚠️  Azure DevOps integration skipped - missing environment variables (AZDO_TOKEN, AZDO_URL)")

            if integrations_created > 0:
                print(f"✅ Created {integrations_created} integration(s) with proper encryption")
            else:
                print("⚠️  No integrations created - configure environment variables and re-run migration if needed")

        except Exception as e:
            print(f"⚠️  Could not create integrations with encrypted credentials: {e}")
            print("💡 You can configure integrations later through the admin interface")

        # Update workflows with JIRA integration_id (now that integrations are created)
        print("📋 Linking workflows to JIRA integration...")

        cursor.execute("SELECT id FROM integrations WHERE name = 'JIRA' AND client_id = %s;", (client_id,))
        jira_integration_result = cursor.fetchone()
        jira_integration_id = jira_integration_result['id'] if jira_integration_result else None

        if jira_integration_id:
            cursor.execute("""
                UPDATE workflows
                SET integration_id = %s
                WHERE client_id = %s AND integration_id IS NULL;
            """, (jira_integration_id, client_id))

            updated_count = cursor.rowcount
            print(f"✅ Linked {updated_count} workflows to JIRA integration (ID: {jira_integration_id})")
        else:
            print("⚠️ JIRA integration not found - workflows will remain unlinked to integration")

        # Get GitHub integration ID for job schedule linking
        cursor.execute("SELECT id FROM integrations WHERE name = 'GITHUB' AND client_id = %s;", (client_id,))
        github_integration_result = cursor.fetchone()
        github_integration_id = github_integration_result['id'] if github_integration_result else None

        # Update all integration-specific tables with proper integration assignments
        print("📋 Assigning integration IDs to all integration-specific tables...")

        if jira_integration_id:
            # JIRA Integration assignments (issue-related tables and configuration)
            tables_for_jira = [
                'projects', 'issuetypes', 'statuses', 'issues', 'issue_changelogs', 'jira_pull_request_links',
                'status_mappings', 'issuetype_hierarchies', 'issuetype_mappings', 'job_schedules'
            ]

            for table in tables_for_jira:
                # Special handling for job_schedules - only assign JIRA jobs to JIRA integration
                if table == 'job_schedules':
                    cursor.execute(f"""
                        UPDATE {table}
                        SET integration_id = %s
                        WHERE client_id = %s AND integration_id IS NULL AND job_name = 'jira_sync';
                    """, (jira_integration_id, client_id))
                else:
                    cursor.execute(f"""
                        UPDATE {table}
                        SET integration_id = %s
                        WHERE client_id = %s AND integration_id IS NULL;
                    """, (jira_integration_id, client_id))

                updated_count = cursor.rowcount
                if updated_count > 0:
                    print(f"   ✅ Linked {updated_count} {table} records to JIRA integration")

        if github_integration_id:
            # GITHUB Integration assignments (repository/PR-related tables)
            tables_for_github = [
                'repositories', 'pull_requests', 'pull_request_reviews',
                'pull_request_commits', 'pull_request_comments'
            ]

            for table in tables_for_github:
                cursor.execute(f"""
                    UPDATE {table}
                    SET integration_id = %s
                    WHERE client_id = %s AND integration_id IS NULL;
                """, (github_integration_id, client_id))

                updated_count = cursor.rowcount
                if updated_count > 0:
                    print(f"   ✅ Linked {updated_count} {table} records to GITHUB integration")

            # Assign GitHub job schedules to GitHub integration
            cursor.execute("""
                UPDATE job_schedules
                SET integration_id = %s
                WHERE client_id = %s AND integration_id IS NULL AND job_name = 'github_sync';
            """, (github_integration_id, client_id))

            github_jobs_updated = cursor.rowcount
            if github_jobs_updated > 0:
                print(f"   ✅ Linked {github_jobs_updated} GitHub job_schedules records to GITHUB integration")

        print("✅ All integration-specific tables properly assigned to integrations")

        # Now make integration_id NOT NULL for all IntegrationBaseEntity tables
        print("📋 Setting integration_id columns to NOT NULL...")
        integration_tables = [
            'workflows', 'status_mappings', 'issuetype_hierarchies', 'issuetype_mappings',
            'repositories', 'pull_requests', 'pull_request_reviews',
            'pull_request_commits', 'pull_request_comments', 'jira_pull_request_links'
        ]

        for table in integration_tables:
            cursor.execute(f"ALTER TABLE {table} ALTER COLUMN integration_id SET NOT NULL;")
            print(f"   ✅ Set {table}.integration_id to NOT NULL")

        # Insert system settings
        print("📋 Creating system settings...")

        system_settings_data = [
            {"setting_key": "orchestrator_interval_minutes", "setting_value": "60", "setting_type": "integer", "description": "Orchestrator run interval in minutes"},
            {"setting_key": "orchestrator_enabled", "setting_value": "true", "setting_type": "boolean", "description": "Enable/disable orchestrator"},
            {"setting_key": "orchestrator_retry_enabled", "setting_value": "true", "setting_type": "boolean", "description": "Enable/disable orchestrator retry logic"},
            {"setting_key": "orchestrator_retry_interval_minutes", "setting_value": "15", "setting_type": "integer", "description": "Orchestrator retry interval in minutes"},
            {"setting_key": "jira_sync_enabled", "setting_value": "true", "setting_type": "boolean", "description": "Enable/disable Jira synchronization"},
            {"setting_key": "github_sync_enabled", "setting_value": "true", "setting_type": "boolean", "description": "Enable/disable GitHub synchronization"},
            {"setting_key": "data_retention_days", "setting_value": "365", "setting_type": "integer", "description": "Number of days to retain data"},
            {"setting_key": "max_concurrent_jobs", "setting_value": "3", "setting_type": "integer", "description": "Maximum number of concurrent jobs"}
        ]

        for setting in system_settings_data:
            cursor.execute("""
                INSERT INTO system_settings (setting_key, setting_value, setting_type, description, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT (setting_key) DO NOTHING;
            """, (setting["setting_key"], setting["setting_value"], setting["setting_type"], setting["description"], client_id))

        print("✅ System settings created")

        # Insert default users
        print("📋 Creating default users...")

        # Use proper bcrypt password hashing (same as auth service)
        import bcrypt

        def hash_password(password):
            """Hash password using bcrypt (same as auth service)."""
            salt = bcrypt.gensalt()
            return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

        default_users_data = [
            {
                "email": "gustavo.quinelato@wexinc.com",
                "password_hash": hash_password("pulse"),
                "first_name": "Gustavo",
                "last_name": "Quinelato",
                "role": "admin",
                "is_admin": True,
                "auth_provider": "local"
            },
            {
                "email": "admin@pulse.com",
                "password_hash": hash_password("pulse"),
                "first_name": "System",
                "last_name": "Administrator",
                "role": "admin",
                "is_admin": True,
                "auth_provider": "local"
            },
            {
                "email": "user@pulse.com",
                "password_hash": hash_password("pulse"),
                "first_name": "Test",
                "last_name": "User",
                "role": "user",
                "is_admin": False,
                "auth_provider": "local"
            },
            {
                "email": "viewer@pulse.com",
                "password_hash": hash_password("pulse"),
                "first_name": "Test",
                "last_name": "Viewer",
                "role": "view",
                "is_admin": False,
                "auth_provider": "local"
            }
        ]

        for user in default_users_data:
            cursor.execute("""
                INSERT INTO users (email, password_hash, first_name, last_name, role, is_admin, auth_provider, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT (email) DO NOTHING;
            """, (user["email"], user["password_hash"], user["first_name"], user["last_name"], user["role"], user["is_admin"], user["auth_provider"], client_id))

        print("✅ Default users created")

        # Insert default user permissions
        print("📋 Creating default user permissions...")

        # Get user IDs for permission assignment
        cursor.execute("SELECT id, email, role FROM users WHERE client_id = %s;", (client_id,))
        users = cursor.fetchall()

        for user in users:
            user_id = user['id']
            user_role = user['role']

            # Define permissions based on role
            if user_role == 'admin':
                permissions = [
                    ('all', 'read', True),
                    ('all', 'write', True),
                    ('all', 'delete', True),
                    ('all', 'admin', True)
                ]
            elif user_role == 'user':
                permissions = [
                    ('dashboard', 'read', True),
                    ('reports', 'read', True),
                    ('comments', 'write', True),
                    ('projects', 'read', True)
                ]
            elif user_role == 'view':
                permissions = [
                    ('dashboard', 'read', True),
                    ('reports', 'read', True)
                ]
            else:
                permissions = []

            # Insert permissions for this user
            for resource, action, granted in permissions:
                cursor.execute("""
                    INSERT INTO user_permissions (user_id, resource, action, granted, client_id, active, created_at, last_updated_at)
                    VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                    ON CONFLICT DO NOTHING;
                """, (user_id, resource, action, granted, client_id))

        print("✅ Default user permissions created")

        # Insert default job schedules
        print("📋 Creating default job schedules...")

        job_schedules_data = [
            {
                "job_name": "jira_sync",
                "status": "PENDING"
            },
            {
                "job_name": "github_sync",
                "status": "NOT_STARTED"
            }
        ]

        for job in job_schedules_data:
            cursor.execute("""
                INSERT INTO job_schedules (job_name, status, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT (job_name) DO NOTHING;
            """, (job["job_name"], job["status"], client_id))

        print("✅ Default job schedules created")

        # Link job schedules to their corresponding integrations
        print("📋 Linking job schedules to integrations...")

        # Integration IDs already retrieved after integration creation

        # Link jira_sync job to Jira integration
        if jira_integration_id:
            cursor.execute("""
                UPDATE job_schedules
                SET integration_id = %s
                WHERE job_name = 'jira_sync' AND client_id = %s;
            """, (jira_integration_id, client_id))
            print(f"✅ Linked jira_sync job to JIRA integration (ID: {jira_integration_id})")
        else:
            print("⚠️ JIRA integration not found - jira_sync job not linked")

        # Link github_sync job to GitHub integration
        if github_integration_id:
            cursor.execute("""
                UPDATE job_schedules
                SET integration_id = %s
                WHERE job_name = 'github_sync' AND client_id = %s;
            """, (github_integration_id, client_id))
            print(f"✅ Linked github_sync job to GITHUB integration (ID: {github_integration_id})")
        else:
            print("⚠️ GITHUB integration not found - github_sync job not linked")

        print("✅ Job schedules linked to integrations")

        # Now make job_schedules.integration_id NOT NULL since all jobs should be linked
        cursor.execute("ALTER TABLE job_schedules ALTER COLUMN integration_id SET NOT NULL;")
        print("✅ Set job_schedules.integration_id to NOT NULL")

        print("✅ All seed data inserted successfully!")

        # Record this migration as applied
        cursor.execute("""
            INSERT INTO migration_history (migration_number, migration_name, applied_at, status)
            VALUES ('001', 'Initial Schema', NOW(), 'applied')
            ON CONFLICT (migration_number)
            DO UPDATE SET applied_at = NOW(), status = 'applied', rollback_at = NULL;
        """)

        print("✅ Migration 001 recorded in migration history")

        # Commit the transaction
        connection.commit()
        print("✅ Migration 001 applied successfully!")
        
    except Exception as e:
        connection.rollback()
        print(f"❌ Error applying migration: {e}")
        raise

def rollback(connection):
    """Rollback the initial schema migration."""
    print("🔄 Rolling back Migration 001: Initial Schema")
    
    cursor = connection.cursor()
    
    try:
        # Drop tables in reverse dependency order
        print("📋 Dropping tables...")
        
        tables_to_drop = [
            'migration_history',
            'jira_pull_request_links',
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
            'issuetype_hierarchies',
            'issuetype_mappings',
            'status_mappings',
            'workflows',
            'projects',
            'integrations',
            'job_schedules',
            'system_settings',
            'user_permissions',
            'user_sessions',
            'users',
            'clients'
        ]
        
        for table in tables_to_drop:
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
            print(f"   Dropped {table}")

        # Note: migration_history table is dropped with other tables, so we can't record the rollback
        # This is intentional since a complete rollback removes all traces of the migration

        # Commit the transaction
        connection.commit()
        print("✅ Migration 001 rolled back successfully!")
        print("📋 Migration history table also dropped - no record of rollback maintained")
        
    except Exception as e:
        connection.rollback()
        print(f"❌ Error rolling back migration: {e}")
        raise

def check_status(connection):
    """Check if migration has been applied."""
    cursor = connection.cursor()

    try:
        # First check if migration_history table exists and has our record
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'migration_history';
        """)

        migration_table_exists = cursor.fetchone() is not None

        if migration_table_exists:
            # Check migration_history table for this migration
            cursor.execute("""
                SELECT status, applied_at
                FROM migration_history
                WHERE migration_number = '001';
            """)

            migration_record = cursor.fetchone()
            if migration_record:
                if migration_record['status'] == 'applied':
                    applied_at = migration_record['applied_at'].strftime('%Y-%m-%d %H:%M:%S')
                    print(f"✅ Migration 001: Applied on {applied_at}")
                    return True
                else:
                    print(f"⚠️  Migration 001: Status = {migration_record['status']}")
                    return False

        # Fallback: Check if core tables exist (for cases where migration_history doesn't exist)
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('clients', 'users', 'integrations', 'projects', 'workflows', 'status_mappings', 'issuetype_hierarchies', 'issuetype_mappings', 'issues', 'repositories', 'job_schedules')
            ORDER BY table_name;
        """)

        existing_tables = [row['table_name'] for row in cursor.fetchall()]
        expected_tables = ['clients', 'workflows', 'integrations', 'issues', 'issuetype_hierarchies', 'issuetype_mappings', 'job_schedules', 'projects', 'repositories', 'status_mappings', 'users']

        if set(existing_tables) == set(expected_tables):
            print("✅ Migration 001: Applied (detected via table existence)")
            return True
        elif len(existing_tables) == 0:
            print("⏸️  Migration 001: Not Applied")
            return False
        else:
            print(f"⚠️  Migration 001: Partially Applied (found: {existing_tables})")
            return False

    except Exception as e:
        print(f"❌ Error checking migration status: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migration 001: Initial Schema")
    parser.add_argument("--apply", action="store_true", help="Apply the migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    parser.add_argument("--status", action="store_true", help="Check migration status")
    
    args = parser.parse_args()
    
    if not any([args.apply, args.rollback, args.status]):
        parser.print_help()
        sys.exit(1)
    
    # Get database connection
    conn = get_database_connection()
    
    try:
        if args.status:
            check_status(conn)
        elif args.apply:
            apply(conn)
        elif args.rollback:
            rollback(conn)
            
    finally:
        conn.close()
