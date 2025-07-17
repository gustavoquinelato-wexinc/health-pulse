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
        return True
    except Exception as e:
        print(f"❌ Failed to recreate tables: {e}")
        return False

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

def initialize_status_mappings_non_interactive():
    """Initialize status mappings without user confirmation."""
    try:
        from app.core.database import get_database
        from app.core.utils import DateTimeHelper
        from app.models.unified_models import StatusMapping, Client

        database = get_database()

        with database.get_session_context() as session:
            # Get the default client (should be the first one)
            default_client = session.query(Client).first()
            if not default_client:
                print("❌ No client found. Please run client initialization first")
                return False

            # Check if any status mappings already exist for this client
            existing_mappings = session.query(StatusMapping).filter(StatusMapping.client_id == default_client.id).count()

            if existing_mappings > 0:
                print(f"✅ Status mappings table already has {existing_mappings} mapping(s) for client {default_client.name}")
                return True

            # Create status mappings from the updated list
            status_mapping_data = [
                #BACKLOG
                {"status_from": "--creation--", "status_to": "Backlog", "status_category": "To Do"},
                {"status_from": "backlog", "status_to": "Backlog", "status_category": "To Do"},
                {"status_from": "new", "status_to": "Backlog", "status_category": "To Do"},
                {"status_from": "open", "status_to": "Backlog", "status_category": "To Do"},
                {"status_from": "created", "status_to": "Backlog", "status_category": "To Do"},
                {"status_from": "(backlog) unprioritized to dos", "status_to": "Backlog", "status_category": "To Do"},

                #REFINEMENT
                {"status_from": "analysis", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "design", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "prerefinement", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "ready to refine", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "refinement", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "refining", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "tech review", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "waiting for refinement", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "in triage", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "pending approval", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "discovery", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "composting", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "onboarding templates", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "templates", "status_to": "Refinement", "status_category": "To Do"},
                {"status_from": "template approval pending", "status_to": "Refinement", "status_category": "To Do"},

                #READY TO WORK
                {"status_from": "approved", "status_to": "Ready to Work", "status_category": "To Do"},
                {"status_from": "ready", "status_to": "Ready to Work", "status_category": "To Do"},
                {"status_from": "ready for development", "status_to": "Ready to Work", "status_category": "To Do"},
                {"status_from": "ready to development", "status_to": "Ready to Work", "status_category": "To Do"},
                {"status_from": "ready to work", "status_to": "Ready to Work", "status_category": "To Do"},
                {"status_from": "refined", "status_to": "Ready to Work", "status_category": "To Do"},
                {"status_from": "proposed", "status_to": "Ready to Work", "status_category": "To Do"},

                #TO DO
                {"status_from": "committed", "status_to": "To Do", "status_category": "To Do"},
                {"status_from": "planned", "status_to": "To Do", "status_category": "To Do"},
                {"status_from": "selected for development", "status_to": "To Do", "status_category": "To Do"},
                {"status_from": "to do", "status_to": "To Do", "status_category": "To Do"},

                #IN PROGRESS
                {"status_from": "active", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "applied to trn", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "blocked", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "building", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "code review", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "codereview", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "coding", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "coding done", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "deployed to dev", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "development", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "in development", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "in progress", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "in review", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "peer review", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "pre-readiness", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "ready for peer review", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "ready to dep to dev", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "review", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "training", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "validated in trn", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "waiting partner", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "on hold", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "pipeline approval pending", "status_to": "In Progress", "status_category": "In Progress"},
                {"status_from": "merging branches", "status_to": "In Progress", "status_category": "In Progress"},

                #READY FOR QA TESTING
                {"status_from": "ready for qa", "status_to": "Ready for Story Testing", "status_category": "Waiting"},
                {"status_from": "ready for qa build", "status_to": "Ready for Story Testing", "status_category": "Waiting"},
                {"status_from": "ready for test", "status_to": "Ready for Story Testing", "status_category": "Waiting"},
                {"status_from": "ready for testing", "status_to": "Ready for Story Testing", "status_category": "Waiting"},
                {"status_from": "ready for story testing", "status_to": "Ready for Story Testing", "status_category": "Waiting"},
                {"status_from": "deploying demo", "status_to": "Ready for Story Testing", "status_category": "Waiting"},

                #IN QA TEST
                {"status_from": "applied to qa", "status_to": "Story Testing", "status_category": "In Progress"},
                {"status_from": "in test", "status_to": "Story Testing", "status_category": "In Progress"},
                {"status_from": "in testing", "status_to": "Story Testing", "status_category": "In Progress"},
                {"status_from": "promoted to qa", "status_to": "Story Testing", "status_category": "In Progress"},
                {"status_from": "qa", "status_to": "Story Testing", "status_category": "In Progress"},
                {"status_from": "qa in progress", "status_to": "Story Testing", "status_category": "In Progress"},
                {"status_from": "test", "status_to": "Story Testing", "status_category": "In Progress"},
                {"status_from": "story testing", "status_to": "Story Testing", "status_category": "In Progress"},
                {"status_from": "testing", "status_to": "Story Testing", "status_category": "In Progress"},

                #READY FOR UAT TESTING
                {"status_from": "ready for uat", "status_to": "Ready for Acceptance", "status_category": "Waiting"},
                {"status_from": "ready for stage", "status_to": "Ready for Acceptance", "status_category": "Waiting"},
                {"status_from": "validated in qa", "status_to": "Ready for Acceptance", "status_category": "Waiting"},
                {"status_from": "ready for demo", "status_to": "Ready for Acceptance", "status_category": "Waiting"},
                {"status_from": "ready for acceptance", "status_to": "Ready for Acceptance", "status_category": "Waiting"},

                #IN UAT TEST
                {"status_from": "applied to stg", "status_to": "Acceptance Testing", "status_category": "In Progress"},
                {"status_from": "applied to uat", "status_to": "Acceptance Testing", "status_category": "In Progress"},
                {"status_from": "in stage testing", "status_to": "Acceptance Testing", "status_category": "In Progress"},
                {"status_from": "promoted to uat", "status_to": "Acceptance Testing", "status_category": "In Progress"},
                {"status_from": "regression testing", "status_to": "Acceptance Testing", "status_category": "In Progress"},
                {"status_from": "release approval pending", "status_to": "Acceptance Testing", "status_category": "In Progress"},
                {"status_from": "uat", "status_to": "Acceptance Testing", "status_category": "In Progress"},
                {"status_from": "acceptance testing", "status_to": "Acceptance Testing", "status_category": "In Progress"},
                {"status_from": "pre production testing", "status_to": "Acceptance Testing", "status_category": "In Progress"},
                {"status_from": "final checks", "status_to": "Acceptance Testing", "status_category": "In Progress"},
                {"status_from": "release testing", "status_to": "Acceptance Testing", "status_category": "In Progress"},

                #READY FOR PROD
                {"status_from": "deploy", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "deployment", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "ready for prod", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "ready for prd", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "ready for production", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "ready for release", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "ready to dep to prod", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "ready to launch", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "release pending", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "resolved", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "validated in stg", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "validated in uat", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "deploying database", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "deploying applications", "status_to": "Ready for Prod", "status_category": "Waiting"},
                {"status_from": "awaiting deployment", "status_to": "Ready for Prod", "status_category": "Waiting"},

                #DONE
                {"status_from": "applied to prod", "status_to": "Done", "status_category": "Done"},
                {"status_from": "applied to prod/trn", "status_to": "Done", "status_category": "Done"},
                {"status_from": "closed", "status_to": "Done", "status_category": "Done"},
                {"status_from": "done", "status_to": "Done", "status_category": "Done"},
                {"status_from": "validated in prod", "status_to": "Done", "status_category": "Done"},
                {"status_from": "released", "status_to": "Done", "status_category": "Done"},
                {"status_from": "deployed to production", "status_to": "Done", "status_category": "Done"},
                {"status_from": "release deployed", "status_to": "Done", "status_category": "Done"},
                {"status_from": "closure", "status_to": "Done", "status_category": "Done"},

                #REMOVED
                {"status_from": "cancelled", "status_to": "Discarded", "status_category": "Discarded"},
                {"status_from": "rejected", "status_to": "Discarded", "status_category": "Discarded"},
                {"status_from": "removed", "status_to": "Discarded", "status_category": "Discarded"},
                {"status_from": "withdrawn", "status_to": "Discarded", "status_category": "Discarded"},
            ]

            mappings_created = 0
            for mapping_data in status_mapping_data:
                status_mapping = StatusMapping(
                    status_from=mapping_data["status_from"],
                    status_to=mapping_data["status_to"],
                    status_category=mapping_data["status_category"],
                    client_id=default_client.id,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                session.add(status_mapping)
                mappings_created += 1

            session.commit()
            print(f"✅ Successfully created {mappings_created} status mappings for client {default_client.name}")

        return True
    except Exception as e:
        print(f"❌ Failed to initialize status mappings: {e}")
        import traceback
        traceback.print_exc()
        return False


def initialize_flow_steps_non_interactive():
    """Initialize flow steps without user confirmation."""
    try:
        from app.core.database import get_database
        from app.core.utils import DateTimeHelper
        from app.models.unified_models import FlowStep, Client

        database = get_database()

        with database.get_session_context() as session:
            # Get the default client (should be the first one)
            default_client = session.query(Client).first()
            if not default_client:
                print("❌ No client found. Please run client initialization first")
                return False

            # Check if any flow steps already exist for this client
            existing_flow_steps = session.query(FlowStep).filter(FlowStep.client_id == default_client.id).count()

            if existing_flow_steps > 0:
                print(f"✅ Flow steps table already has {existing_flow_steps} flow step(s) for client {default_client.name}")
                return True

            # Create standardized flow steps
            flow_steps_data = [
                {"mapped_name": "Backlog", "step_category": "To Do"},
                {"mapped_name": "Refinement", "step_category": "To Do"},
                {"mapped_name": "Ready to Work", "step_category": "To Do"},
                {"mapped_name": "To Do", "step_category": "To Do"},
                {"mapped_name": "In Progress", "step_category": "In Progress"},
                {"mapped_name": "Ready for Story Testing", "step_category": "Waiting"},
                {"mapped_name": "Story Testing", "step_category": "In Progress"},
                {"mapped_name": "Ready for Acceptance", "step_category": "Waiting"},
                {"mapped_name": "Acceptance Testing", "step_category": "In Progress"},
                {"mapped_name": "Ready for Prod", "step_category": "Waiting"},
                {"mapped_name": "Done", "step_category": "Done"},
                {"mapped_name": "Discarded", "step_category": "Discarded"},
            ]

            flow_steps_created = 0
            for step_data in flow_steps_data:
                flow_step = FlowStep(
                    mapped_name=step_data["mapped_name"],
                    step_category=step_data["step_category"],
                    client_id=default_client.id,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                session.add(flow_step)
                flow_steps_created += 1

            session.commit()
            print(f"✅ Successfully created {flow_steps_created} flow steps for client {default_client.name}")

        return True
    except Exception as e:
        print(f"❌ Failed to initialize flow steps: {e}")
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
                    name="Jira",
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
                    name="GitHub",
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
                    name="Aha!",
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
                    name="Azure DevOps",
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
            print("   • Max concurrent jobs: 1")
            print("   • Job timeout: 120 minutes")
        else:
            print("❌ Failed to initialize system settings")

        return success

    except Exception as e:
        print(f"❌ Failed to initialize system settings: {e}")
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
        print("   • Database is ready for new data")
        print()
        print("💡 Next steps:")
        print("   • Run the ETL service to start data extraction")
        print("   • Or use the admin API to manage data")
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
        print("   • Use 'python utils/initialize_integrations.py' to add integrations")
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
        status_mappings_success = initialize_status_mappings_non_interactive()
        flow_steps_success = initialize_flow_steps_non_interactive()
        integration_success = initialize_integrations_non_interactive()

        # Initialize job schedules for orchestration
        print("🔧 Initializing job schedules...")
        from app.jobs.orchestrator import initialize_job_schedules
        job_schedules_success = initialize_job_schedules()

        # Initialize system settings for orchestrator configuration
        print("🔧 Initializing system settings...")
        system_settings_success = initialize_system_settings_non_interactive()

        print_final_summary(True, True, integration_success and flow_steps_success and status_mappings_success and job_schedules_success and system_settings_success)

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
            print("💡 Use 'python utils/initialize_integrations.py' to add integrations")
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
                status_mappings_success = initialize_status_mappings_non_interactive()
                flow_steps_success = initialize_flow_steps_non_interactive()
                integration_success = initialize_integrations()
                integration_success = integration_success and flow_steps_success and status_mappings_success

                # Initialize job schedules for orchestration
                print("🔧 Initializing job schedules...")
                from app.jobs.orchestrator import initialize_job_schedules
                job_schedules_success = initialize_job_schedules()

                # Initialize system settings for orchestrator configuration
                print("🔧 Initializing system settings...")
                system_settings_success = initialize_system_settings_non_interactive()

                integration_success = integration_success and job_schedules_success and system_settings_success

            print_final_summary(success, recreate_success, integration_success)
        else:
            print("\n❌ Database reset failed!")
            print("💡 Check the error messages above and try again")
            sys.exit(1)

if __name__ == "__main__":
    main()
