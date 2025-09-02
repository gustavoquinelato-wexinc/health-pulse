#!/usr/bin/env python3
"""
Migration 0002: Initial Seed Data Apple
Description: Inserts initial seed data for Apple client including DORA benchmarks, clients, integrations, workflows, status mappings, users, and system settings
Author: Pulse Platform Team
Date: 2025-08-18
"""

import os
import sys
import argparse
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

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
        return connection
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}")
        raise

def apply(connection):
    """Apply the migration."""
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        print("🚀 Applying Migration 0003: Initial Seed Data Apple")

        # 1. Insert default client (Apple)
        print("📋 Creating Apple client...")
        cursor.execute("""
            INSERT INTO clients (name, website, assets_folder, logo_filename, color_schema_mode, active, created_at, last_updated_at)
            VALUES ('Apple', 'https://www.apple.com', 'apple', 'logo.png', 'default', TRUE, NOW(), NOW())
            ON CONFLICT DO NOTHING;
        """)

        # Get the client ID for seed data
        cursor.execute("SELECT id FROM clients WHERE name = 'Apple' LIMIT 1;")
        client_result = cursor.fetchone()
        if not client_result:
            raise Exception("Failed to create or find Apple client")
        client_id = client_result['id']
        print(f"   ✅ Apple client created/found with ID: {client_id}")

        # 3. Create integrations (JIRA and GitHub only)
        print("📋 Creating integrations...")

        # Get credentials from environment if available
        try:
            # Load environment variables from .env file
            from dotenv import load_dotenv
            import os

            # Try to find .env file in multiple locations
            env_paths = [
                os.path.join(os.path.dirname(__file__), '..', '.env'),  # services/backend-service/.env
                os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '.env'),  # project root/.env
            ]

            print(f"   🔍 DEBUG - Looking for .env files:")
            for i, env_path in enumerate(env_paths):
                abs_path = os.path.abspath(env_path)
                exists = os.path.exists(env_path)
                print(f"   🔍 Path {i+1}: {abs_path} - Exists: {exists}")

            env_loaded = False
            for env_path in env_paths:
                if os.path.exists(env_path):
                    load_dotenv(env_path)
                    print(f"   📋 Loading credentials from: {os.path.abspath(env_path)}")
                    env_loaded = True
                    break

            if not env_loaded:
                print("   ⚠️  No .env file found, using system environment variables")

            from app.core.config import Settings
            from app.core.config import AppConfig
            settings = Settings()

            # Try to load encryption key
            try:
                key = AppConfig.load_key()
                encryption_available = True
                print("   🔐 Encryption available - tokens will be encrypted")
            except Exception as e:
                print(f"   ⚠️  Encryption key not available: {e}")
                encryption_available = False

        except Exception as e:
            print(f"   ⚠️  Could not load settings: {e}")
            settings = None
            encryption_available = False

        # JIRA Integration - Reading credentials from .env file
        jira_url = os.getenv('JIRA_URL')
        jira_username = os.getenv('JIRA_USERNAME')
        jira_token = os.getenv('JIRA_TOKEN')
        jira_password = None
        jira_active = False

        if jira_url and jira_username and jira_token:
            print(f"   📋 Found JIRA credentials in .env: {jira_url}, {jira_username}")
            try:
                if encryption_available:
                    key = AppConfig.load_key()
                    jira_password = AppConfig.encrypt_token(jira_token, key)
                    print("   🔐 JIRA token encrypted successfully")
                    jira_active = True
                else:
                    jira_password = jira_token
                    print("   ⚠️  JIRA token stored unencrypted (AppConfig not available)")
                    jira_active = True
            except Exception as e:
                print(f"   ❌ Failed to process JIRA credentials: {e}")
                jira_active = False
        else:
            print("   ⚠️  JIRA credentials not found in .env file")
            # Use default values for inactive integration
            jira_url = "https://wexinc.atlassian.net"
            jira_username = "gustavo.quinelato@wexinc.com"

        cursor.execute("""
            INSERT INTO integrations (name, url, username, password, base_search, last_sync_at, client_id, active, created_at, last_updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (name, client_id) DO NOTHING
            RETURNING id;
        """, ("JIRA", jira_url, jira_username, jira_password, "project in (BDP,BEN,BEX,BST,CDB,CDH,EPE,FG,HBA,HDO,HDS)", "2000-01-01 00:00:00", client_id, jira_active))

        jira_result = cursor.fetchone()
        if jira_result:
            jira_integration_id = jira_result['id']
        else:
            cursor.execute("SELECT id FROM integrations WHERE name = 'JIRA' AND client_id = %s;", (client_id,))
            jira_integration_id = cursor.fetchone()['id']

        print(f"   ✅ JIRA integration created (ID: {jira_integration_id}, active: {jira_active})")

        # GitHub Integration - Reading credentials from .env file
        github_token = os.getenv('GITHUB_TOKEN')
        github_password = None
        github_active = False

        if github_token:
            print(f"   📋 Found GitHub token in .env: {github_token[:10]}...")
            try:
                if encryption_available:
                    key = AppConfig.load_key()
                    github_password = AppConfig.encrypt_token(github_token, key)
                    print("   🔐 GitHub token encrypted successfully")
                    github_active = True
                else:
                    github_password = github_token
                    print("   ⚠️  GitHub token stored unencrypted (AppConfig not available)")
                    github_active = True
            except Exception as e:
                print(f"   ❌ Failed to process GitHub credentials: {e}")
                github_active = False
        else:
            print("   ⚠️  GitHub token not found in .env file")

        cursor.execute("""
            INSERT INTO integrations (name, url, username, password, base_search, last_sync_at, client_id, active, created_at, last_updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (name, client_id) DO NOTHING
            RETURNING id;
        """, ("GITHUB", "https://api.github.com", None, github_password, "health-", "2000-01-01 00:00:00", client_id, github_active))

        github_result = cursor.fetchone()
        if github_result:
            github_integration_id = github_result['id']
        else:
            cursor.execute("SELECT id FROM integrations WHERE name = 'GITHUB' AND client_id = %s;", (client_id,))
            github_integration_id = cursor.fetchone()['id']

        print(f"   ✅ GitHub integration created (ID: {github_integration_id}, active: {github_active})")
        print("✅ Integrations created")

        # 4. Insert workflow steps (complete workflow configuration - EXACT COPY from 001_initial_schema.py)
        print("📋 Creating workflow steps...")
        workflow_steps_data = [
            {"step_name": "Backlog", "step_number": 1, "category": "To Do", "is_commitment_point": False},
            {"step_name": "Refinement", "step_number": 2, "category": "To Do", "is_commitment_point": False},
            {"step_name": "Ready to Work", "step_number": 3, "category": "To Do", "is_commitment_point": False},
            {"step_name": "To Do", "step_number": 4, "category": "To Do", "is_commitment_point": True},  # Commitment point
            {"step_name": "In Progress", "step_number": 5, "category": "In Progress", "is_commitment_point": False},
            {"step_name": "Ready for Story Testing", "step_number": 6, "category": "Waiting", "is_commitment_point": False},
            {"step_name": "Story Testing", "step_number": 7, "category": "In Progress", "is_commitment_point": False},
            {"step_name": "Ready for Acceptance", "step_number": 8, "category": "Waiting", "is_commitment_point": False},
            {"step_name": "Acceptance Testing", "step_number": 9, "category": "In Progress", "is_commitment_point": False},
            {"step_name": "Ready for Prod", "step_number": 10, "category": "Waiting", "is_commitment_point": False},
            {"step_name": "Done", "step_number": 11, "category": "Done", "is_commitment_point": False},
            {"step_name": "Discarded", "step_number": None, "category": "Discarded", "is_commitment_point": False}  # No step number for Discarded
        ]

        workflow_ids = {}
        for step in workflow_steps_data:
            step_name = step["step_name"]
            step_number = step["step_number"]
            category = step["category"]
            is_commitment_point = step["is_commitment_point"]

            cursor.execute("""
                INSERT INTO workflows (step_name, step_number, step_category, is_commitment_point, integration_id, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT DO NOTHING
                RETURNING id;
            """, (step_name, step_number, category, is_commitment_point, jira_integration_id, client_id))

            result = cursor.fetchone()
            if result:
                workflow_ids[step_name] = result['id']
            else:
                # Get existing ID if conflict occurred
                cursor.execute("SELECT id FROM workflows WHERE step_name = %s AND client_id = %s;", (step_name, client_id))
                existing_result = cursor.fetchone()
                if existing_result:
                    workflow_ids[step_name] = existing_result['id']

        print("✅ Workflow steps created")

        # 5. Insert status mappings (complete workflow configuration - EXACT COPY from 001_initial_schema.py)
        print("📋 Creating status mappings...")
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
                INSERT INTO status_mappings (status_from, status_to, status_category, workflow_id, integration_id, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT (status_from, client_id) DO NOTHING;
            """, (mapping["status_from"], mapping["status_to"], mapping["status_category"], workflow_id, jira_integration_id, client_id))

        print("✅ Status mappings inserted")

        # 6. Insert issuetype hierarchies
        print("📋 Creating issuetype hierarchies...")
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
                INSERT INTO issuetype_hierarchies (level_name, level_number, description, integration_id, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT DO NOTHING;
            """, (hierarchy["level_name"], hierarchy["level_number"], hierarchy["description"], jira_integration_id, client_id))

        print("✅ Issuetype hierarchies inserted")

        # 7. Insert issuetype mappings
        print("📋 Creating issuetype mappings...")
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

            #BUG (PROD)
            {"issuetype_from": "Bug", "issuetype_to": "Bug", "hierarchy_level": 0},

            #INCIDENT
            {"issuetype_from": "Issue", "issuetype_to": "Incident", "hierarchy_level": 0},
            {"issuetype_from": "Incident", "issuetype_to": "Incident", "hierarchy_level": 0},

            #SPIKE
            {"issuetype_from": "Spike", "issuetype_to": "Spike", "hierarchy_level": 0},

            #DEFECT (NON-PROD)
            {"issuetype_from": "Defect", "issuetype_to": "Defect", "hierarchy_level": -1},
            {"issuetype_from": "Sub-task", "issuetype_to": "Sub-task", "hierarchy_level": -1},
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
                    INSERT INTO issuetype_mappings (issuetype_from, issuetype_to, issuetype_hierarchy_id, integration_id, client_id, active, created_at, last_updated_at)
                    VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                    ON CONFLICT (issuetype_from, client_id) DO NOTHING;
                """, (mapping["issuetype_from"], mapping["issuetype_to"], hierarchy_id, jira_integration_id, client_id))

        print("✅ Issuetype mappings inserted")

        # 8. Insert system settings
        print("📋 Creating system settings...")
        system_settings_data = [
            {"setting_key": "orchestrator_interval_minutes", "setting_value": "60", "setting_type": "integer", "description": "Orchestrator run interval in minutes"},
            {"setting_key": "orchestrator_enabled", "setting_value": "true", "setting_type": "boolean", "description": "Enable/disable orchestrator"},
            {"setting_key": "orchestrator_retry_enabled", "setting_value": "true", "setting_type": "boolean", "description": "Enable/disable orchestrator retry logic"},
            {"setting_key": "orchestrator_retry_interval_minutes", "setting_value": "15", "setting_type": "integer", "description": "Orchestrator retry interval in minutes"},
            {"setting_key": "jira_sync_enabled", "setting_value": "true", "setting_type": "boolean", "description": "Enable/disable Jira synchronization"},
            {"setting_key": "github_sync_enabled", "setting_value": "true", "setting_type": "boolean", "description": "Enable/disable GitHub synchronization"},
            {"setting_key": "data_retention_days", "setting_value": "365", "setting_type": "integer", "description": "Number of days to retain data"},
            {"setting_key": "max_concurrent_jobs", "setting_value": "3", "setting_type": "integer", "description": "Maximum number of concurrent jobs"},
            {"setting_key": "font_contrast_threshold", "setting_value": "0.5", "setting_type": "decimal", "description": "Font contrast threshold for color calculations"},
            {"setting_key": "contrast_ratio_normal", "setting_value": "4.5", "setting_type": "decimal", "description": "WCAG contrast ratio for normal text (AA: 4.5, AAA: 7.0)"},
            {"setting_key": "contrast_ratio_large", "setting_value": "3.0", "setting_type": "decimal", "description": "WCAG contrast ratio for large text (AA: 3.0, AAA: 4.5)"}
        ]

        for setting in system_settings_data:
            cursor.execute("""
                INSERT INTO system_settings (setting_key, setting_value, setting_type, description, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT (setting_key, client_id) DO NOTHING;
            """, (setting["setting_key"], setting["setting_value"], setting["setting_type"], setting["description"], client_id))

        print("✅ System settings created")

        # 9. Insert default users
        print("📋 Creating default users...")

        # Import bcrypt for password hashing
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
                "role": "viewer",
                "is_admin": False,
                "auth_provider": "local"
            }
        ]

        for user in default_users_data:
            cursor.execute("""
                INSERT INTO users (email, password_hash, first_name, last_name, role, is_admin, auth_provider, theme_mode, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT (email) DO NOTHING;
            """, (user["email"], user["password_hash"], user["first_name"], user["last_name"], user["role"], user["is_admin"], user["auth_provider"], 'light', client_id))

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

        # 10. Create default job schedules
        print("📋 Creating default job schedules...")

        # Integration IDs already available from previous steps

        job_schedules_data = [
            {
                "job_name": "jira_sync",
                "status": "PENDING",
                "integration_id": jira_integration_id
            },
            {
                "job_name": "github_sync",
                "status": "NOT_STARTED",
                "integration_id": github_integration_id
            }
        ]

        for job in job_schedules_data:
            cursor.execute("""
                INSERT INTO job_schedules (job_name, status, integration_id, client_id, active, created_at, last_updated_at)
                VALUES (%s, %s, %s, %s, TRUE, NOW(), NOW())
                ON CONFLICT (job_name) DO NOTHING;
            """, (job["job_name"], job["status"], job["integration_id"], client_id))

        print("✅ Default job schedules created")

        # 11. Insert color settings for Apple client
        print("📋 Creating color settings for Apple client...")

        # Color calculation functions (inline)
        def _luminance(hex_color):
            """Calculate WCAG relative luminance"""
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))

            def _linearize(c):
                return (c/12.92) if c <= 0.03928 else ((c+0.055)/1.055) ** 2.4

            return 0.2126*_linearize(r) + 0.7152*_linearize(g) + 0.0722*_linearize(b)

        def _pick_on_color(hex_color):
            """Use 0.5 threshold for font color selection"""
            luminance = _luminance(hex_color)
            return '#FFFFFF' if luminance < 0.5 else '#000000'

        def _pick_on_gradient(color_a, color_b):
            """Choose best font color for gradient pair"""
            on_a = _pick_on_color(color_a)
            on_b = _pick_on_color(color_b)
            return on_a if on_a == on_b else '#FFFFFF'  # Default to white if different

        def _get_accessible_color(hex_color, accessibility_level='AA'):
            """Create accessibility-enhanced color with improved AAA contrast"""
            if accessibility_level == 'AAA':
                # Use 30% darkening for better visual distinction (from fix_aaa_colors.py)
                hex_color = hex_color.lstrip('#')
                r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                r = max(0, int(r * 0.7))  # 30% darker
                g = max(0, int(g * 0.7))
                b = max(0, int(b * 0.7))
                return f"#{r:02x}{g:02x}{b:02x}"
            else:
                return hex_color  # AA level uses original color

        def calculate_color_variants(base_colors):
            """Calculate all color variants"""
            variants = {}

            # On-colors (5 columns)
            for i in range(1, 6):
                variants[f'on_color{i}'] = _pick_on_color(base_colors[f'color{i}'])

            # Gradient on-colors (5 combinations including 5→1)
            gradient_pairs = [
                ('color1', 'color2', 'on_gradient_1_2'),
                ('color2', 'color3', 'on_gradient_2_3'),
                ('color3', 'color4', 'on_gradient_3_4'),
                ('color4', 'color5', 'on_gradient_4_5'),
                ('color5', 'color1', 'on_gradient_5_1')
            ]

            for color_a_key, color_b_key, gradient_key in gradient_pairs:
                variants[gradient_key] = _pick_on_gradient(base_colors[color_a_key], base_colors[color_b_key])

            return variants

        # Apple color definitions
        DEFAULT_COLORS = {
            'light': {'color1': '#2862EB', 'color2': '#763DED', 'color3': '#059669', 'color4': '#0EA5E9', 'color5': '#F59E0B'},
            'dark': {'color1': '#2862EB', 'color2': '#763DED', 'color3': '#059669', 'color4': '#0EA5E9', 'color5': '#F59E0B'}
        }

        APPLE_CUSTOM_COLORS = {
            'light': {'color1': '#007AFF', 'color2': '#000000', 'color3': '#34C759', 'color4': '#FF9500', 'color5': '#FF3B30'},
            'dark': {'color1': '#007AFF', 'color2': '#000000', 'color3': '#34C759', 'color4': '#FF9500', 'color5': '#FF3B30'}
        }

        # Insert 12 rows for Apple: 2 modes × 3 accessibility levels × 2 themes
        for mode in ['default', 'custom']:
            for accessibility_level in ['regular', 'AA', 'AAA']:
                for theme_mode in ['light', 'dark']:

                    # Get base colors for this configuration
                    if mode == 'default':
                        base_colors = DEFAULT_COLORS[theme_mode]
                    else:
                        base_colors = APPLE_CUSTOM_COLORS[theme_mode]

                    # Apply accessibility enhancement if needed
                    if accessibility_level != 'regular':
                        enhanced_colors = {}
                        for i in range(1, 6):
                            enhanced_colors[f'color{i}'] = _get_accessible_color(base_colors[f'color{i}'], accessibility_level)
                    else:
                        enhanced_colors = base_colors

                    # Calculate variants
                    calculated_variants = calculate_color_variants(enhanced_colors)

                    # Insert row
                    cursor.execute("""
                        INSERT INTO client_color_settings (
                            color_schema_mode, accessibility_level, theme_mode,
                            color1, color2, color3, color4, color5,
                            on_color1, on_color2, on_color3, on_color4, on_color5,
                            on_gradient_1_2, on_gradient_2_3, on_gradient_3_4, on_gradient_4_5, on_gradient_5_1,
                            client_id, active, created_at, last_updated_at
                        ) VALUES (
                            %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, TRUE, NOW(), NOW()
                        ) ON CONFLICT (client_id, color_schema_mode, accessibility_level, theme_mode) DO NOTHING;
                    """, (
                        mode, accessibility_level, theme_mode,
                        enhanced_colors['color1'], enhanced_colors['color2'], enhanced_colors['color3'], enhanced_colors['color4'], enhanced_colors['color5'],
                        calculated_variants['on_color1'], calculated_variants['on_color2'], calculated_variants['on_color3'], calculated_variants['on_color4'], calculated_variants['on_color5'],
                        calculated_variants['on_gradient_1_2'], calculated_variants['on_gradient_2_3'], calculated_variants['on_gradient_3_4'], calculated_variants['on_gradient_4_5'], calculated_variants['on_gradient_5_1'],
                        client_id
                    ))

        print("✅ Color settings created for Apple client")
        print("✅ Apple client seed data completed successfully")

        # Record this migration as applied
        cursor.execute("""
            INSERT INTO migration_history (migration_number, migration_name, applied_at, status)
            VALUES (%s, %s, NOW(), 'applied')
            ON CONFLICT (migration_number)
            DO UPDATE SET applied_at = NOW(), status = 'applied', rollback_at = NULL;
        """, ('0003', 'Initial Seed Data Apple'))

        connection.commit()
        print(f"SUCCESS: Migration 0003 applied successfully")

    except Exception as e:
        connection.rollback()
        print(f"ERROR: Error applying migration: {e}")
        raise

def rollback(connection):
    """Rollback the migration."""
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        print("🔄 Rolling back Migration 0003: Initial Seed Data Apple")

        # Delete seed data in reverse order of creation, handling foreign key constraints properly
        print("📋 Removing job schedules...")
        cursor.execute("DELETE FROM job_schedules WHERE job_name IN ('jira_sync', 'github_sync');")

        print("📋 Removing user permissions...")
        cursor.execute("DELETE FROM user_permissions WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        print("📋 Removing user sessions...")
        cursor.execute("DELETE FROM user_sessions WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        print("📋 Removing default users...")
        cursor.execute("DELETE FROM users WHERE email IN ('gustavo.quinelato@wexinc.com', 'admin@pulse.com', 'user@pulse.com', 'viewer@pulse.com');")

        print("📋 Removing system settings...")
        cursor.execute("DELETE FROM system_settings WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        # Remove data tables in correct dependency order
        print("📋 Removing data that references other tables...")
        # First: Remove leaf tables (no other tables depend on them)
        cursor.execute("DELETE FROM pull_request_reviews WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")
        cursor.execute("DELETE FROM pull_request_commits WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")
        cursor.execute("DELETE FROM pull_request_comments WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")
        cursor.execute("DELETE FROM issue_changelogs WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")
        cursor.execute("DELETE FROM jira_pull_request_links WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        # Second: Remove tables that depend on issues/repositories
        cursor.execute("DELETE FROM pull_requests WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        # Third: Remove issues (depends on issuetypes, statuses, projects)
        cursor.execute("DELETE FROM issues WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        # Fourth: Remove many-to-many relationship tables
        print("📋 Removing relationship tables...")
        cursor.execute("""
            DELETE FROM projects_issuetypes
            WHERE project_id IN (SELECT id FROM projects WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple'))
        """)
        cursor.execute("""
            DELETE FROM projects_statuses
            WHERE project_id IN (SELECT id FROM projects WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple'))
        """)

        # Fifth: Remove repositories and projects
        cursor.execute("DELETE FROM repositories WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")
        cursor.execute("DELETE FROM projects WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        # Sixth: Remove issuetypes and statuses (depend on mappings)
        cursor.execute("DELETE FROM issuetypes WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")
        cursor.execute("DELETE FROM statuses WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        print("📋 Removing issuetype mappings...")
        cursor.execute("DELETE FROM issuetype_mappings WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        print("📋 Removing issuetype hierarchies...")
        cursor.execute("DELETE FROM issuetype_hierarchies WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        print("📋 Removing status mappings...")
        cursor.execute("DELETE FROM status_mappings WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        print("📋 Removing workflows...")
        cursor.execute("DELETE FROM workflows WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        print("📋 Removing all integrations for Apple client...")
        cursor.execute("DELETE FROM integrations WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        print("📋 Removing color settings...")
        cursor.execute("DELETE FROM client_color_settings WHERE client_id IN (SELECT id FROM clients WHERE name = 'Apple');")

        print("📋 Removing Apple client...")
        cursor.execute("DELETE FROM clients WHERE name = 'Apple';")

        print("✅ Seed data removed successfully")

        # Record this migration as rolled back
        cursor.execute("""
            UPDATE migration_history
            SET rollback_at = NOW(), status = 'rolled_back'
            WHERE migration_number = %s;
        """, ('0003',))

        connection.commit()
        print(f"SUCCESS: Migration 0003 rolled back successfully")

    except Exception as e:
        connection.rollback()
        print(f"ERROR: Error rolling back migration: {e}")
        raise

def check_status(connection):
    """Check if this migration has been applied."""
    cursor = connection.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("""
            SELECT migration_number, migration_name, applied_at, rollback_at, status
            FROM migration_history
            WHERE migration_number = %s;
        """, ('0002',))

        result = cursor.fetchone()
        if result:
            status = result['status']
            if status == 'applied':
                print(f"SUCCESS: Migration 0002 is applied ({result['applied_at']})")
            elif status == 'rolled_back':
                print(f"ROLLBACK: Migration 0002 was rolled back ({result['rollback_at']})")
        else:
            print(f"PENDING: Migration 0002 has not been applied")

    except Exception as e:
        print(f"ERROR: Error checking migration status: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migration 0003: Initial Seed Data Apple")
    parser.add_argument("--apply", action="store_true", help="Apply the migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    parser.add_argument("--status", action="store_true", help="Check migration status")

    args = parser.parse_args()

    if not any([args.apply, args.rollback, args.status]):
        parser.print_help()
        sys.exit(1)

    try:
        conn = get_database_connection()

        if args.apply:
            apply(conn)
        elif args.rollback:
            rollback(conn)
        elif args.status:
            check_status(conn)

        conn.close()

    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        sys.exit(1)
