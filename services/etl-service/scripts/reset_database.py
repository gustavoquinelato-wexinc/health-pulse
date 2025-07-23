#!/usr/bin/env python3
"""
Database Reset Script for ETL Service.
This script will DROP ALL tables from your PostgreSQL database.

⚠️  WARNING: This will permanently delete ALL data in your database!
Use this only when you want to start completely fresh.

Usage:
    python scripts/reset_database.py [options]

Examples:
    # Interactive mode (default)
    python scripts/reset_database.py

    # Complete reset with all options (non-interactive)
    python scripts/reset_database.py --all

    # Just drop tables (non-interactive)
    python scripts/reset_database.py --drop-only

    # Drop and recreate tables (non-interactive)
    python scripts/reset_database.py --recreate-tables
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to Python path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Setup basic logging early to suppress SQLAlchemy logs before any imports
# Use simple format to avoid conflicts with app's structured logging
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings and errors from libraries
    format='%(message)s',   # Simple format for cleaner output
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Disable SQLAlchemy logging completely for cleaner output
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)  # Only show errors
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.orm').setLevel(logging.ERROR)

# Suppress SQLAlchemy warnings completely
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, module='sqlalchemy')
warnings.filterwarnings('ignore', message='.*relationship.*will copy column.*')
warnings.filterwarnings('ignore', message='.*overlaps.*')

# Override DEBUG setting to disable SQLAlchemy echo for reset_database
import os
os.environ['DEBUG'] = 'false'

from app.core.database import get_database
from app.core.config import get_settings

# Suppress app's database logging after import
logging.getLogger('app.core.database').setLevel(logging.ERROR)
logging.getLogger('app.jobs.orchestrator').setLevel(logging.ERROR)

def confirm_reset():
    """Ask for user confirmation before proceeding."""
    print("⚠️  WARNING: DATABASE RESET")
    print("=" * 60)
    print("This script will permanently delete:")
    print("• ALL tables and their data")
    print("• ALL sequences")
    print("• This action CANNOT be undone!")
    print()
    
    settings = get_settings()
    print(f"Target Database: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DATABASE}")
    print(f"Target User: {settings.POSTGRES_USER}")
    print()
    
    # First confirmation
    response1 = input("Are you sure you want to proceed? (type 'yes' to continue): ").strip().lower()
    if response1 != 'yes':
        print("❌ Operation cancelled")
        return False
    
    # Second confirmation
    print()
    print("🚨 FINAL WARNING: This will delete ALL your data!")
    response2 = input("Type 'DELETE ALL DATA' to confirm: ").strip()
    if response2 != 'DELETE ALL DATA':
        print("❌ Operation cancelled")
        return False
    
    return True

def reset_database():
    """Reset the database by dropping all tables and sequences."""
    print("\n🔄 Starting database reset...")
    
    try:
        # Initialize database
        database = get_database()

        if not database.is_connection_alive():
            print("❌ Database connection failed")
            return False
            
        print("✅ Database connection successful")
        
        # Use the existing drop_tables method which handles both tables and sequences
        print("🗑️  Dropping all tables and sequences...")
        database.drop_tables()
        
        print("✅ All tables and sequences dropped successfully")
        print("🎉 Database reset completed!")
        
        return True
        
    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def recreate_tables():
    """Optionally recreate the table structure."""
    print("\n📋 Do you want to recreate the table structure?")
    response = input("Type 'yes' to recreate tables (or 'no' to skip): ").strip().lower()

    if response == 'yes':
        try:
            database = get_database()
            print("🔄 Creating tables...")
            database.create_tables()
            print("✅ Tables created successfully")
            print("💡 Database is ready for fresh data")

            # Record migration 001 as applied since we created the same schema
            record_migration_001_applied()

            return True
        except Exception as e:
            print(f"❌ Failed to recreate tables: {e}")
            return False
    else:
        print("ℹ️  Skipped table recreation")
        print("💡 Run the application or use admin API to create tables when needed")
        return True

def initialize_clients():
    """Initialize the clients table with a default client."""
    print("\n🔧 Initializing clients...")
    return initialize_clients_non_interactive()

def initialize_integrations():
    """Optionally initialize integration data."""
    print("\n🔧 Do you want to initialize integration data?")
    print("   This will create Jira, GitHub, Aha!, and Azure DevOps integrations")
    print("   with encrypted tokens from your .env configuration.")
    response = input("Type 'yes' to initialize integrations (or 'no' to skip): ").strip().lower()

    if response == 'yes':
        return initialize_integrations_non_interactive()
    else:
        print("⏭️  Skipping integration initialization")
        return True

def reset_database_non_interactive():
    """Reset the database without user confirmation."""
    print("🔄 Starting database reset...")

    try:
        # Initialize database
        database = get_database()

        if not database.is_connection_alive():
            print("❌ Database connection failed")
            return False

        print("✅ Database connection successful")

        # Use the existing drop_tables method which handles both tables and sequences
        print("🗑️  Dropping all tables and sequences...")
        database.drop_tables()

        print("✅ All tables and sequences dropped successfully")
        return True

    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def recreate_tables_non_interactive():
    """Recreate tables without user confirmation."""
    try:
        database = get_database()
        print("🔄 Creating tables...")
        database.create_tables()
        print("✅ Tables created successfully")

        # Record migration 001 as applied since we created the same schema
        record_migration_001_applied()

        return True
    except Exception as e:
        print(f"❌ Failed to recreate tables: {e}")
        return False

def record_migration_001_applied():
    """Record migration 001 as applied in migration_history table."""
    try:
        from app.core.database import get_database
        from sqlalchemy import text

        database = get_database()
        print("📋 Recording migration 001 as applied...")

        with database.get_session_context() as session:
            # Use raw SQL to insert migration record
            session.execute(text("""
                INSERT INTO migration_history (migration_number, migration_name, applied_at, status)
                VALUES ('001', 'Initial Schema', NOW(), 'applied')
                ON CONFLICT (migration_number)
                DO UPDATE SET applied_at = NOW(), status = 'applied', rollback_at = NULL;
            """))
            session.commit()

        print("✅ Migration 001 recorded as applied")
        print("💡 Migration system will recognize this as already applied")

    except Exception as e:
        print(f"⚠️  Warning: Could not record migration 001: {e}")
        print("💡 You may need to manually apply migration 001 later")

def initialize_clients_non_interactive():
    """Initialize clients without user confirmation."""
    try:
        from app.core.database import get_database
        from app.core.utils import DateTimeHelper
        from app.models.unified_models import Client
        from datetime import datetime

        database = get_database()

        with database.get_session_context() as session:
            # Check if any clients already exist
            existing_clients = session.query(Client).count()

            if existing_clients > 0:
                print(f"✅ Clients table already has {existing_clients} client(s)")
                return True

            # Create default client
            default_client = Client(
                name="WEX",
                website="https://www.wexinc.com",
                active=True,
                created_at=DateTimeHelper.now_utc(),
                last_updated_at=DateTimeHelper.now_utc()
            )

            session.add(default_client)
            session.commit()

            print("✅ Successfully created default client:")
            print(f"   ID: {default_client.id}")
            print(f"   Name: {default_client.name}")
            print(f"   Website: {default_client.website}")
            print(f"   Active: {default_client.active}")

        return True
    except Exception as e:
        print(f"❌ Failed to initialize clients: {e}")
        import traceback
        traceback.print_exc()
        return False

def initialize_workflow_configuration_non_interactive():
    """Initialize flow steps, status mappings, and issuetype mappings from workflow configuration."""
    try:
        from app.core.database import get_database
        from app.core.utils import DateTimeHelper
        from app.models.unified_models import StatusMapping, Client, FlowStep, IssuetypeMapping, IssuetypeHierarchy

        database = get_database()

        with database.get_session_context() as session:
            # Get the default client (should be the first one)
            default_client = session.query(Client).first()
            if not default_client:
                print("❌ No client found. Please run client initialization first")
                return False

            # Check if workflow configuration already exists for this client
            existing_flow_steps = session.query(FlowStep).filter(FlowStep.client_id == default_client.id).count()
            existing_status_mappings = session.query(StatusMapping).filter(StatusMapping.client_id == default_client.id).count()
            existing_issuetype_hierarchies = session.query(IssuetypeHierarchy).filter(IssuetypeHierarchy.client_id == default_client.id).count()
            existing_issuetype_mappings = session.query(IssuetypeMapping).filter(IssuetypeMapping.client_id == default_client.id).count()

            print(f"📊 Existing data check: {existing_flow_steps} flow steps, {existing_status_mappings} status mappings, {existing_issuetype_hierarchies} issuetype hierarchies, {existing_issuetype_mappings} issuetype mappings")

            if existing_flow_steps > 0 and existing_status_mappings > 0 and existing_issuetype_hierarchies > 0 and existing_issuetype_mappings > 0:
                print(f"✅ Workflow configuration already exists: {existing_flow_steps} flow steps, {existing_status_mappings} status mappings, {existing_issuetype_hierarchies} issuetype hierarchies, {existing_issuetype_mappings} issuetype mappings for client {default_client.name}")
                return True

            # Step 1: Extract unique flow steps from workflow configuration
            # Combined workflow configuration data
            workflow_configuration_data = [
                #BACKLOG
                {"status_from": "Backlog", "status_to": "Backlog", "status_category": "To Do", "flow_step": "Backlog"},
                {"status_from": "New", "status_to": "Backlog", "status_category": "To Do", "flow_step": "Backlog"},
                {"status_from": "Open", "status_to": "Backlog", "status_category": "To Do", "flow_step": "Backlog"},
                {"status_from": "Created", "status_to": "Backlog", "status_category": "To Do", "flow_step": "Backlog"},

                #REFINEMENT
                {"status_from": "Analysis", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Design", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Prerefinement", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Ready to Refine", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Refinement", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Refining", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Tech Review", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Waiting for refinement", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "In Triage", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Pending Approval", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Discovery", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Composting", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Onboarding Templates", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Templates", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},
                {"status_from": "Template Approval Pending", "status_to": "Refinement", "status_category": "To Do", "flow_step": "Refinement"},

                #READY TO WORK
                {"status_from": "Approved", "status_to": "Ready to Work", "status_category": "To Do", "flow_step": "Ready to Work"},
                {"status_from": "Ready", "status_to": "Ready to Work", "status_category": "To Do", "flow_step": "Ready to Work"},
                {"status_from": "Ready for Development", "status_to": "Ready to Work", "status_category": "To Do", "flow_step": "Ready to Work"},
                {"status_from": "Ready to Development", "status_to": "Ready to Work", "status_category": "To Do", "flow_step": "Ready to Work"},
                {"status_from": "Ready to Work", "status_to": "Ready to Work", "status_category": "To Do", "flow_step": "Ready to Work"},
                {"status_from": "Refined", "status_to": "Ready to Work", "status_category": "To Do", "flow_step": "Ready to Work"},
                {"status_from": "Proposed", "status_to": "Ready to Work", "status_category": "To Do", "flow_step": "Ready to Work"},

                #TO DO
                {"status_from": "Committed", "status_to": "To Do", "status_category": "To Do", "flow_step": "To Do"},
                {"status_from": "Planned", "status_to": "To Do", "status_category": "To Do", "flow_step": "To Do"},
                {"status_from": "Selected for development", "status_to": "To Do", "status_category": "To Do", "flow_step": "To Do"},
                {"status_from": "To Do", "status_to": "To Do", "status_category": "To Do", "flow_step": "To Do"},

                #IN PROGRESS
                {"status_from": "Active", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Applied to TRN", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Blocked", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Building", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Code Review", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Codereview", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Coding", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Coding Done", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Deployed to Dev", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Development", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "In Development", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "In Progress", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "In Review", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Peer Review", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Pre-readiness", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Ready for Peer Review", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Ready to Dep to Dev", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Review", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Training", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Validated in TRN", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Waiting Partner", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "On Hold", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Pipeline Approval Pending", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},
                {"status_from": "Merging Branches", "status_to": "In Progress", "status_category": "In Progress", "flow_step": "In Progress"},

                #READY FOR QA TESTING
                {"status_from": "Ready for QA", "status_to": "Ready for Story Testing", "status_category": "Waiting", "flow_step": "Ready for Story Testing"},
                {"status_from": "Ready for QA build", "status_to": "Ready for Story Testing", "status_category": "Waiting", "flow_step": "Ready for Story Testing"},
                {"status_from": "Ready for Test", "status_to": "Ready for Story Testing", "status_category": "Waiting", "flow_step": "Ready for Story Testing"},
                {"status_from": "Ready for Testing", "status_to": "Ready for Story Testing", "status_category": "Waiting", "flow_step": "Ready for Story Testing"},
                {"status_from": "Ready for Story Testing", "status_to": "Ready for Story Testing", "status_category": "Waiting", "flow_step": "Ready for Story Testing"},
                {"status_from": "Deploying Demo", "status_to": "Ready for Story Testing", "status_category": "Waiting", "flow_step": "Ready for Story Testing"},

                #IN QA TEST
                {"status_from": "Applied to QA", "status_to": "Story Testing", "status_category": "In Progress", "flow_step": "Story Testing"},
                {"status_from": "In Test", "status_to": "Story Testing", "status_category": "In Progress", "flow_step": "Story Testing"},
                {"status_from": "In Testing", "status_to": "Story Testing", "status_category": "In Progress", "flow_step": "Story Testing"},
                {"status_from": "Promoted to QA", "status_to": "Story Testing", "status_category": "In Progress", "flow_step": "Story Testing"},
                {"status_from": "QA", "status_to": "Story Testing", "status_category": "In Progress", "flow_step": "Story Testing"},
                {"status_from": "QA in Progress", "status_to": "Story Testing", "status_category": "In Progress", "flow_step": "Story Testing"},
                {"status_from": "Test", "status_to": "Story Testing", "status_category": "In Progress", "flow_step": "Story Testing"},
                {"status_from": "Story Testing", "status_to": "Story Testing", "status_category": "In Progress", "flow_step": "Story Testing"},
                {"status_from": "Testing", "status_to": "Story Testing", "status_category": "In Progress", "flow_step": "Story Testing"},

                #READY FOR UAT TESTING
                {"status_from": "Ready for Uat", "status_to": "Ready for Acceptance", "status_category": "Waiting", "flow_step": "Ready for Acceptance"},
                {"status_from": "Ready for Stage", "status_to": "Ready for Acceptance", "status_category": "Waiting", "flow_step": "Ready for Acceptance"},
                {"status_from": "Validated in QA", "status_to": "Ready for Acceptance", "status_category": "Waiting", "flow_step": "Ready for Acceptance"},
                {"status_from": "Ready for Demo", "status_to": "Ready for Acceptance", "status_category": "Waiting", "flow_step": "Ready for Acceptance"},
                {"status_from": "Ready for Acceptance", "status_to": "Ready for Acceptance", "status_category": "Waiting", "flow_step": "Ready for Acceptance"},

                #IN UAT TEST
                {"status_from": "Applied to STG", "status_to": "Acceptance Testing", "status_category": "In Progress", "flow_step": "Acceptance Testing"},
                {"status_from": "Applied to UAT", "status_to": "Acceptance Testing", "status_category": "In Progress", "flow_step": "Acceptance Testing"},
                {"status_from": "In Stage Testing", "status_to": "Acceptance Testing", "status_category": "In Progress", "flow_step": "Acceptance Testing"},
                {"status_from": "Promoted to UAT", "status_to": "Acceptance Testing", "status_category": "In Progress", "flow_step": "Acceptance Testing"},
                {"status_from": "Regression Testing", "status_to": "Acceptance Testing", "status_category": "In Progress", "flow_step": "Acceptance Testing"},
                {"status_from": "Release Approval Pending", "status_to": "Acceptance Testing", "status_category": "In Progress", "flow_step": "Acceptance Testing"},
                {"status_from": "UAT", "status_to": "Acceptance Testing", "status_category": "In Progress", "flow_step": "Acceptance Testing"},
                {"status_from": "Acceptance Testing", "status_to": "Acceptance Testing", "status_category": "In Progress", "flow_step": "Acceptance Testing"},
                {"status_from": "Pre Production Testing", "status_to": "Acceptance Testing", "status_category": "In Progress", "flow_step": "Acceptance Testing"},
                {"status_from": "Final Checks", "status_to": "Acceptance Testing", "status_category": "In Progress", "flow_step": "Acceptance Testing"},
                {"status_from": "Release Testing", "status_to": "Acceptance Testing", "status_category": "In Progress", "flow_step": "Acceptance Testing"},

                #READY FOR PROD
                {"status_from": "Deploy", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Deployment", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Ready for prod", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Ready for prd", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Ready for production", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Ready for Release", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Ready to Dep to Prod", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Ready to Launch", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Release Pending", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Resolved", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Validated in STG", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Validated in UAT", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Deploying Database", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Deploying Applications", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},
                {"status_from": "Awaiting Deployment", "status_to": "Ready for Prod", "status_category": "Waiting", "flow_step": "Ready for Prod"},

                #DONE
                {"status_from": "Applied to Prod", "status_to": "Done", "status_category": "Done", "flow_step": "Done"},
                {"status_from": "Applied to Prod/TRN", "status_to": "Done", "status_category": "Done", "flow_step": "Done"},
                {"status_from": "Closed", "status_to": "Done", "status_category": "Done", "flow_step": "Done"},
                {"status_from": "Done", "status_to": "Done", "status_category": "Done", "flow_step": "Done"},
                {"status_from": "Validated in Prod", "status_to": "Done", "status_category": "Done", "flow_step": "Done"},
                {"status_from": "Released", "status_to": "Done", "status_category": "Done", "flow_step": "Done"},
                {"status_from": "Deployed to Production", "status_to": "Done", "status_category": "Done", "flow_step": "Done"},
                {"status_from": "Release Deployed", "status_to": "Done", "status_category": "Done", "flow_step": "Done"},
                {"status_from": "Closure", "status_to": "Done", "status_category": "Done", "flow_step": "Done"},

                #REMOVED
                {"status_from": "Cancelled", "status_to": "Discarded", "status_category": "Discarded", "flow_step": "Discarded"},
                {"status_from": "Rejected", "status_to": "Discarded", "status_category": "Discarded", "flow_step": "Discarded"},
                {"status_from": "Removed", "status_to": "Discarded", "status_category": "Discarded", "flow_step": "Discarded"},
                {"status_from": "Withdrawn", "status_to": "Discarded", "status_category": "Discarded", "flow_step": "Discarded"},
            ]

            # Issue type hierarchy configuration
            issuetype_hierarchy_data = [
                {"level_name": "Capital Investment", "level_number": 4, "description": "Capital Investment / Theme"},
                {"level_name": "Product Objective", "level_number": 3, "description": "Product Objective / Initiative Name"},
                {"level_name": "Milestone", "level_number": 2, "description": "Milestone"},
                {"level_name": "Epic", "level_number": 1, "description": "Big chunk of work"},
                {"level_name": "Story", "level_number": 0, "description": "Small chunk of work"},
                {"level_name": "Sub-task", "level_number": -1, "description": "Internal Checklist Points"}
            ]

            # Issue type mapping configuration
            issuetype_mapping_data = [
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

            # Step 1: Extract unique flow steps and create them first
            unique_flow_steps = {}
            for mapping in workflow_configuration_data:
                flow_step_name = mapping["flow_step"]
                if flow_step_name not in unique_flow_steps:
                    # Determine step_category from the first occurrence
                    unique_flow_steps[flow_step_name] = mapping["status_category"]

            # Create flow steps with predefined order
            flow_step_order = [
                ("Backlog", 1), ("Refinement", 2), ("Ready to Work", 3), ("To Do", 4),
                ("In Progress", 5), ("Ready for Story Testing", 6), ("Story Testing", 7),
                ("Ready for Acceptance", 8), ("Acceptance Testing", 9), ("Ready for Prod", 10),
                ("Done", 11), ("Discarded", None)  # No step number for Discarded
            ]

            flow_steps_created = 0
            flow_step_lookup = {}
            for flow_step_name, step_number in flow_step_order:
                if flow_step_name in unique_flow_steps:
                    step_category = unique_flow_steps[flow_step_name]
                    flow_step = FlowStep(
                        name=flow_step_name,
                        step_number=step_number,
                        step_category=step_category,
                        client_id=default_client.id,
                        created_at=DateTimeHelper.now_utc(),
                        last_updated_at=DateTimeHelper.now_utc()
                    )
                session.add(flow_step)
                session.flush()  # Get the ID immediately
                flow_step_lookup[flow_step_name] = flow_step.id
                flow_steps_created += 1

            # Step 2: Create status mappings with flow_step_id references
            mappings_created = 0
            for mapping_data in workflow_configuration_data:
                flow_step_id = flow_step_lookup.get(mapping_data["flow_step"])

                status_mapping = StatusMapping(
                    status_from=mapping_data["status_from"],
                    status_to=mapping_data["status_to"],
                    status_category=mapping_data["status_category"],
                    flow_step_id=flow_step_id,  # Foreign key relationship
                    client_id=default_client.id,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                session.add(status_mapping)
                mappings_created += 1

            # Step 3: Create issuetype hierarchies
            issuetype_hierarchies_created = 0
            for hierarchy_data in issuetype_hierarchy_data:
                issuetype_hierarchy = IssuetypeHierarchy(
                    level_name=hierarchy_data["level_name"],
                    level_number=hierarchy_data["level_number"],
                    description=hierarchy_data["description"],
                    client_id=default_client.id,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                session.add(issuetype_hierarchy)
                issuetype_hierarchies_created += 1
                print(f"   ✅ Created hierarchy: {hierarchy_data['level_name']} (Level {hierarchy_data['level_number']})")

            # Flush session to make hierarchies visible for queries
            session.flush()

            # Step 4: Create issuetype mappings with hierarchy links
            issuetype_mappings_created = 0
            for mapping_data in issuetype_mapping_data:
                # Find the corresponding hierarchy
                hierarchy = session.query(IssuetypeHierarchy).filter(
                    IssuetypeHierarchy.level_number == mapping_data["hierarchy_level"],
                    IssuetypeHierarchy.client_id == default_client.id
                ).first()

                if hierarchy:
                    issuetype_mapping = IssuetypeMapping(
                        issuetype_from=mapping_data["issuetype_from"],
                        issuetype_to=mapping_data["issuetype_to"],
                        issuetype_hierarchy_id=hierarchy.id,
                        client_id=default_client.id,
                        created_at=DateTimeHelper.now_utc(),
                        last_updated_at=DateTimeHelper.now_utc()
                    )
                    session.add(issuetype_mapping)
                    issuetype_mappings_created += 1
                    print(f"   ✅ Created mapping: {mapping_data['issuetype_from']} → {mapping_data['issuetype_to']} (Level {mapping_data['hierarchy_level']})")
                else:
                    print(f"   ❌ No hierarchy found for level {mapping_data['hierarchy_level']} - skipping {mapping_data['issuetype_from']}")

            session.commit()
            print(f"✅ Successfully created {flow_steps_created} flow steps, {mappings_created} status mappings, {issuetype_hierarchies_created} issuetype hierarchies, and {issuetype_mappings_created} issuetype mappings for client {default_client.name}")

        return True
    except Exception as e:
        print(f"❌ Failed to initialize status mappings: {e}")
        import traceback
        traceback.print_exc()
        return False



def initialize_integrations_non_interactive():
    """Initialize integrations without user confirmation."""
    try:
        # Import here to avoid circular imports
        from app.core.config import get_settings, AppConfig
        from app.core.database import get_database
        from app.core.utils import DateTimeHelper
        from app.models.unified_models import Integration, Client
        from datetime import datetime

        settings = get_settings()
        database = get_database()
        key = AppConfig.load_key()

        print("🔄 Initializing integrations...")

        with database.get_session_context() as session:
            # Get the default client (should be the first one)
            default_client = session.query(Client).first()
            if not default_client:
                print("❌ No client found. Please run 'python utils/initialize_clients.py' first")
                return False

            integrations_created = 0

            # Create Jira integration (required)
            if settings.JIRA_URL and settings.JIRA_USERNAME and settings.JIRA_TOKEN:
                # Set Jira last_sync_at to today at 12:00 PM Central Time
                today_noon = DateTimeHelper.now_central().replace(hour=12, minute=0, second=0, microsecond=0)

                jira_integration = Integration(
                    name="JIRA",
                    url=settings.JIRA_URL,
                    username=settings.JIRA_USERNAME,
                    password=AppConfig.encrypt_token(settings.JIRA_TOKEN, key),
                    last_sync_at=today_noon,
                    client_id=default_client.id,
                    active=True,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                session.add(jira_integration)
                integrations_created += 1
                print("   ✅ Jira integration created")

            # Create GitHub integration (optional)
            if settings.GITHUB_TOKEN:
                github_integration = Integration(
                    name="GITHUB",
                    url="https://api.github.com",
                    username=None,
                    password=AppConfig.encrypt_token(settings.GITHUB_TOKEN, key),
                    last_sync_at=datetime(2000, 1, 1),
                    client_id=default_client.id,
                    active=True,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                session.add(github_integration)
                integrations_created += 1
                print("   ✅ GitHub integration created")

            # Create Aha! integration (optional)
            if settings.AHA_TOKEN and settings.AHA_URL:
                aha_integration = Integration(
                    name="AHA!",
                    url=settings.AHA_URL,
                    username=None,
                    password=AppConfig.encrypt_token(settings.AHA_TOKEN, key),
                    last_sync_at=datetime(1900, 1, 1),
                    client_id=default_client.id,
                    active=True,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                session.add(aha_integration)
                integrations_created += 1
                print("   ✅ Aha! integration created")

            # Create Azure DevOps integration (optional)
            if settings.AZDO_TOKEN and settings.AZDO_URL:
                azdo_integration = Integration(
                    name="AZURE DEVOPS",
                    url=settings.AZDO_URL,
                    username=None,
                    password=AppConfig.encrypt_token(settings.AZDO_TOKEN, key),
                    last_sync_at=datetime(1900, 1, 1),
                    client_id=default_client.id,
                    active=True,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                session.add(azdo_integration)
                integrations_created += 1
                print("   ✅ Azure DevOps integration created")

            session.commit()
            print(f"✅ {integrations_created} integrations initialized successfully")

        return True
    except Exception as e:
        print(f"❌ Failed to initialize integrations: {e}")
        import traceback
        traceback.print_exc()
        return False


def initialize_system_settings_non_interactive():
    """Initialize system settings without user confirmation."""
    try:
        from app.core.settings_manager import SettingsManager

        print("🔄 Initializing system settings...")

        # Initialize default settings in database
        success = SettingsManager.initialize_default_settings()

        if success:
            print("✅ System settings initialized successfully")
            print("   • Orchestrator interval: 60 minutes")
            print("   • Orchestrator enabled: True")
            print("   • Orchestrator retry enabled: True")
            print("   • Orchestrator retry interval: 15 minutes")
            print("   • Orchestrator max retry attempts: 3")
            print("   • Max concurrent jobs: 1")
            print("   • Job timeout: 120 minutes")
            print("   • GitHub GraphQL batch size: 50 PRs per request")
            print("   • GitHub request timeout: 60 seconds")
        else:
            print("❌ Failed to initialize system settings")

        return success

    except Exception as e:
        print(f"❌ Failed to initialize system settings: {e}")
        import traceback
        traceback.print_exc()
        return False


def initialize_default_users_non_interactive():
    """Initialize default users for authentication without user confirmation."""
    try:
        import asyncio
        from app.auth.auth_service import get_auth_service

        print("👥 Creating default users...")

        # Default users to create with new 3-role system
        default_users = [
            {
                "email": "gustavo.quinelato@wexinc.com",
                "password": "pulse",
                "first_name": "Gustavo",
                "last_name": "Quinelato",
                "role": "admin",
                "is_admin": True
            },
            {
                "email": "admin@pulse.com",
                "password": "pulse",
                "first_name": "System",
                "last_name": "Administrator",
                "role": "admin",
                "is_admin": True
            },
            {
                "email": "user@pulse.com",
                "password": "pulse",
                "first_name": "Test",
                "last_name": "User",
                "role": "user",
                "is_admin": False
            },
            {
                "email": "viewer@pulse.com",
                "password": "pulse",
                "first_name": "Test",
                "last_name": "Viewer",
                "role": "view",
                "is_admin": False
            }
        ]

        auth_service = get_auth_service()

        async def create_users():
            # Get the default client (WEX) - should be client_id = 1
            from app.models.unified_models import Client
            from app.core.database import get_database

            database = get_database()
            with database.get_session_context() as session:
                default_client = session.query(Client).filter(Client.name == 'WEX').first()
                if not default_client:
                    print(f"   ❌ Default client 'WEX' not found. Cannot create users.")
                    return

                client_id = default_client.id
                print(f"   📋 Using client: {default_client.name} (ID: {client_id})")

            for user_data in default_users:
                user = await auth_service.create_user(
                    email=user_data["email"],
                    password=user_data["password"],
                    client_id=client_id,
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    role=user_data["role"],
                    is_admin=user_data["is_admin"]
                )

                if user:
                    print(f"   ✅ Created user: {user_data['email']} (role: {user_data['role']})")
                else:
                    print(f"   ⚠️  User already exists or failed to create: {user_data['email']}")

        # Run the async function
        asyncio.run(create_users())

        print("✅ Default users initialization completed")
        return True

    except Exception as e:
        print(f"❌ Failed to initialize default users: {e}")
        import traceback
        traceback.print_exc()
        return False


def initialize_user_permissions_non_interactive():
    """Initialize sample user permissions to demonstrate the permission system."""
    try:
        from app.core.database import get_database
        from app.models.unified_models import User, UserPermission, Client
        from app.auth.permissions import Role, Resource, Action

        print("🔐 Setting up user permissions...")

        database = get_database()
        with database.get_session_context() as session:
            # Get the default client
            default_client = session.query(Client).filter(Client.name == 'WEX').first()
            if not default_client:
                print("   ❌ Default client 'WEX' not found. Cannot create permissions.")
                return False

            client_id = default_client.id

            # Get test user (non-admin user for demonstration)
            test_user = session.query(User).filter(
                User.email == 'user@pulse.com',
                User.client_id == client_id
            ).first()

            if test_user:
                # Grant additional permission to test user (e.g., log download)
                existing_permission = session.query(UserPermission).filter(
                    UserPermission.user_id == test_user.id,
                    UserPermission.resource == Resource.LOG_DOWNLOAD.value,
                    UserPermission.action == Action.EXECUTE.value
                ).first()

                if not existing_permission:
                    permission = UserPermission(
                        user_id=test_user.id,
                        resource=Resource.LOG_DOWNLOAD.value,
                        action=Action.EXECUTE.value,
                        client_id=client_id,
                        active=True
                    )
                    session.add(permission)
                    print(f"   ✅ Granted log download permission to {test_user.email}")
                else:
                    print(f"   ⚠️  Log download permission already exists for {test_user.email}")

            session.commit()

        print("✅ User permissions initialization completed")
        return True

    except Exception as e:
        print(f"❌ Failed to initialize user permissions: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_final_summary(reset_success, recreate_success, integration_success):
    """Print final summary of operations."""
    print("\n" + "=" * 60)
    if reset_success and recreate_success and integration_success:
        print("🎉 Database reset completed successfully!")
        print()
        print("✅ What happened:")
        print("   • All old tables and sequences were dropped")
        print("   • Fresh table structure was created")
        print("   • Integration data was initialized")
        print("   • Default users and roles were created")
        print("   • User permissions were configured")
        print("   • Database is ready for new data")
        print()
        print("👥 Default Users Created:")
        print("   • gustavo.quinelato@wexinc.com (admin) - password: pulse")
        print("   • admin@pulse.com (admin) - password: pulse")
        print("   • user@pulse.com (user) - password: pulse")
        print("   • viewer@pulse.com (view) - password: pulse")
        print()
        print("🔐 Role Permissions:")
        print("   • admin: Full system access and job control")
        print("   • user: Dashboard access, no job control")
        print("   • view: Read-only dashboard access")
        print()
        print("💡 Next steps:")
        print("   • Login at http://localhost:8000/login")
        print("   • Use admin panel at http://localhost:8000/admin")
        print("   • Run ETL jobs from the dashboard")
    elif reset_success and recreate_success and not integration_success:
        print("⚠️  Database reset completed with warnings")
        print()
        print("✅ What happened:")
        print("   • All old tables and sequences were dropped")
        print("   • Fresh table structure was created")
        print("❌ What failed:")
        print("   • Integration initialization had issues")
        print()
        print("💡 Next steps:")
        print("   • Run 'python scripts/reset_database.py --all' to reinitialize everything")
        print("   • Or run the ETL service to create initial data")
    elif reset_success and not recreate_success:
        print("⚠️  Database reset completed with warnings")
        print()
        print("✅ What happened:")
        print("   • All old tables and sequences were dropped")
        print("❌ What failed:")
        print("   • Table recreation had issues")
        print()
        print("💡 Next steps:")
        print("   • Run the ETL service to create tables and initial data")
        print("   • Or use the admin API: POST /admin/database/create-tables")
    else:
        print("❌ Database reset failed!")
        print("💡 Check the error messages above and try again")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="ETL Service Database Reset Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--all', action='store_true',
                       help='⚠️  DESTRUCTIVE: Complete reset - drop tables, recreate, and initialize integrations (non-interactive)')
    parser.add_argument('--drop-only', action='store_true',
                       help='⚠️  DESTRUCTIVE: Only drop tables and sequences (non-interactive)')
    parser.add_argument('--recreate-tables', action='store_true',
                       help='Drop tables, recreate them, but skip integration initialization (non-interactive)')

    args = parser.parse_args()

    print("🗑️  ETL Service Database Reset Tool")
    print("=" * 60)

    # Check if we can connect to database
    try:
        settings = get_settings()
        print(f"🔍 Target: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DATABASE}")
        print()
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print("💡 Make sure your .env file is properly configured")
        sys.exit(1)

    # Handle different modes
    if args.all:
        print("🚀 Running complete reset (non-interactive mode)")
        print("   • Drop all tables and sequences")
        print("   • Recreate table structure")
        print("   • Initialize integrations")
        print()

        # Perform complete reset without confirmation
        success = reset_database_non_interactive()
        if not success:
            sys.exit(1)

        recreate_success = recreate_tables_non_interactive()
        if not recreate_success:
            sys.exit(1)

        clients_success = initialize_clients_non_interactive()
        workflow_success = initialize_workflow_configuration_non_interactive()  # Create flow steps, status mappings, and issuetype mappings
        integration_success = initialize_integrations_non_interactive()

        # Initialize job schedules for orchestration
        print("🔧 Initializing job schedules...")
        from app.jobs.orchestrator import initialize_job_schedules
        job_schedules_success = initialize_job_schedules()

        # Initialize system settings for orchestrator configuration
        print("🔧 Initializing system settings...")
        system_settings_success = initialize_system_settings_non_interactive()

        # Initialize default users for authentication
        print("🔧 Initializing default users...")
        users_success = initialize_default_users_non_interactive()

        # Initialize user permissions
        print("🔧 Initializing user permissions...")
        permissions_success = initialize_user_permissions_non_interactive()

        print_final_summary(True, True, integration_success and workflow_success and job_schedules_success and system_settings_success and users_success and permissions_success)

    elif args.drop_only:
        print("🗑️  Running drop-only mode (non-interactive)")
        print("   • Drop all tables and sequences only")
        print()

        success = reset_database_non_interactive()
        if success:
            print("✅ Tables and sequences dropped successfully")
            print("💡 Use --recreate-tables to recreate structure")
        else:
            sys.exit(1)

    elif args.recreate_tables:
        print("🔄 Running recreate tables mode (non-interactive)")
        print("   • Drop all tables and sequences")
        print("   • Recreate table structure")
        print()

        success = reset_database_non_interactive()
        if not success:
            sys.exit(1)

        recreate_success = recreate_tables_non_interactive()
        if recreate_success:
            print("✅ Tables recreated successfully")
            print("💡 Use 'python scripts/reset_database.py --all' to initialize integrations")
        else:
            sys.exit(1)
    else:
        # Interactive mode (default)
        print("🔧 Running interactive mode")
        print("   You will be prompted for each step")
        print()

        # Get user confirmation
        if not confirm_reset():
            print("\n👋 Database reset cancelled - no changes made")
            sys.exit(0)

        # Perform the reset
        success = reset_database()

        if success:
            # Optionally recreate tables
            recreate_success = recreate_tables()

            # Optionally initialize clients and integrations if tables were created
            integration_success = True
            if recreate_success:
                clients_success = initialize_clients()
                workflow_success = initialize_workflow_configuration_non_interactive()  # Create flow steps, status mappings, and issuetype mappings
                integration_success = initialize_integrations()
                integration_success = integration_success and workflow_success

                # Initialize job schedules for orchestration
                print("🔧 Initializing job schedules...")
                from app.jobs.orchestrator import initialize_job_schedules
                job_schedules_success = initialize_job_schedules()

                # Initialize system settings for orchestrator configuration
                print("🔧 Initializing system settings...")
                system_settings_success = initialize_system_settings_non_interactive()

                # Initialize default users for authentication
                print("🔧 Initializing default users...")
                users_success = initialize_default_users_non_interactive()

                # Initialize user permissions
                print("🔧 Initializing user permissions...")
                permissions_success = initialize_user_permissions_non_interactive()

                integration_success = integration_success and job_schedules_success and system_settings_success and users_success and permissions_success

            print_final_summary(success, recreate_success, integration_success)
        else:
            print("\n❌ Database reset failed!")
            print("💡 Check the error messages above and try again")
            sys.exit(1)

if __name__ == "__main__":
    main()
