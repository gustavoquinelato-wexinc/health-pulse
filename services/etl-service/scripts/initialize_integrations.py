#!/usr/bin/env python3
"""
Initialize Integrations Data Script

This script initializes all configured integrations (Jira, GitHub, Aha!, Azure DevOps)
in the database with encrypted tokens. It can be used for:
- First-time setup
- Re-initializing integrations after database reset
- Adding new integrations to existing database

Usage:
    python scripts/initialize_integrations.py [options]

Examples:
    # Initialize all configured integrations
    python scripts/initialize_integrations.py

    # Force re-initialize (overwrite existing)
    python scripts/initialize_integrations.py --force

    # Initialize specific integration only
    python scripts/initialize_integrations.py --integration jira

    # Dry run (show what would be done)
    python scripts/initialize_integrations.py --dry-run
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Add the parent directory to Python path for imports
script_dir = Path(__file__).parent
etl_service_dir = script_dir.parent

# Always ensure we have the correct etl-service directory
if etl_service_dir.name == 'etl-service':
    pass
else:
    # Look for etl-service directory relative to the script location
    current_path = Path(__file__).resolve()
    
    # Walk up the directory tree to find etl-service
    for parent in current_path.parents:
        if parent.name == 'etl-service':
            etl_service_dir = parent
            break
    else:
        # If we still can't find it, try from current working directory
        cwd = Path.cwd()
        if cwd.name == 'etl-service':
            etl_service_dir = cwd
        elif (cwd / 'services' / 'etl-service').exists():
            etl_service_dir = cwd / 'services' / 'etl-service'
        else:
            raise RuntimeError(f"Cannot find etl-service directory. Script location: {current_path}, Current working directory: {cwd}")

# Add to Python path
sys.path.insert(0, str(etl_service_dir))

def setup_logging(debug: bool = False):
    """Setup logging configuration using the main app's colored logging."""
    import logging

    try:
        # Import and use the main app's colored logging configuration
        from app.core.logging_config import setup_logging as app_setup_logging
        app_setup_logging()
        print("✅ Using colored logging configuration")
    except ImportError:
        # Fallback to basic logging if app modules aren't available
        level = logging.DEBUG if debug else logging.INFO

        # Create logs directory if it doesn't exist
        logs_dir = etl_service_dir / 'logs'
        logs_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(logs_dir / 'initialize_integrations.log')
            ]
        )
        print("⚠️  Using basic logging configuration (colored logging not available)")

    # Reduce noise from external libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

def get_configured_integrations() -> List[dict]:
    """Get list of configured integrations from settings."""
    from app.core.config import get_settings
    
    settings = get_settings()
    integrations = []
    
    # Jira (required)
    if settings.JIRA_URL and settings.JIRA_USERNAME and settings.JIRA_TOKEN:
        integrations.append({
            'name': 'Jira',
            'url': settings.JIRA_URL,
            'username': settings.JIRA_USERNAME,
            'token': settings.JIRA_TOKEN,
            'required': True
        })
    
    # GitHub (optional)
    if settings.GITHUB_TOKEN:
        integrations.append({
            'name': 'GitHub',
            'url': 'https://api.github.com',
            'username': None,
            'token': settings.GITHUB_TOKEN,
            'required': False
        })
    
    # Aha! (optional)
    if settings.AHA_TOKEN and settings.AHA_URL:
        integrations.append({
            'name': 'Aha!',
            'url': settings.AHA_URL,
            'username': None,
            'token': settings.AHA_TOKEN,
            'required': False
        })
    
    # Azure DevOps (optional)
    if settings.AZDO_TOKEN and settings.AZDO_URL:
        integrations.append({
            'name': 'Azure DevOps',
            'url': settings.AZDO_URL,
            'username': None,
            'token': settings.AZDO_TOKEN,
            'required': False
        })
    
    return integrations

def check_existing_integrations() -> dict:
    """Check which integrations already exist in the database."""
    from app.core.database import get_database
    from app.models.unified_models import Integration
    
    database = get_database()
    existing = {}
    
    try:
        with database.get_session_context() as session:
            integrations = session.query(Integration).all()
            for integration in integrations:
                existing[integration.name] = {
                    'id': integration.id,
                    'url': integration.url,
                    'username': integration.username,
                    'last_sync': integration.last_sync_at
                }
    except Exception as e:
        print(f"⚠️  Could not check existing integrations: {e}")
        return {}
    
    return existing

def initialize_integration(integration_config: dict, force: bool = False, dry_run: bool = False) -> bool:
    """Initialize a single integration."""
    from app.core.database import get_database
    from app.models.unified_models import Integration, Client
    from app.core.config import AppConfig
    
    name = integration_config['name']
    
    if dry_run:
        print(f"🔍 [DRY RUN] Would initialize {name} integration:")
        print(f"   URL: {integration_config['url']}")
        print(f"   Username: {integration_config.get('username', 'None')}")
        print(f"   Token: {'*' * 20}...")
        return True
    
    try:
        database = get_database()
        key = AppConfig.load_key()
        
        with database.get_session_context() as session:
            # Get the default client (should be the first one)
            default_client = session.query(Client).first()
            if not default_client:
                print(f"❌ No client found. Please run 'python utils/initialize_clients.py' first")
                return False

            # Check if integration already exists
            existing = session.query(Integration).filter(Integration.name == name).first()
            
            if existing and not force:
                print(f"⚠️  {name} integration already exists (ID: {existing.id})")
                print(f"   Use --force to overwrite")
                return False
            
            if existing and force:
                print(f"🔄 Updating existing {name} integration...")
                existing.url = integration_config['url']
                existing.username = integration_config.get('username')
                existing.password = AppConfig.encrypt_token(integration_config['token'], key)
                existing.last_updated_at = datetime.now()
                session.commit()
                print(f"✅ {name} integration updated successfully")
            else:
                print(f"➕ Creating new {name} integration...")
                new_integration = Integration(
                    name=name,
                    url=integration_config['url'],
                    username=integration_config.get('username'),
                    password=AppConfig.encrypt_token(integration_config['token'], key),
                    last_sync_at=datetime(1900, 1, 1),
                    client_id=default_client.id,
                    active=True,
                    created_at=datetime.now(),
                    last_updated_at=datetime.now()
                )
                session.add(new_integration)
                session.commit()
                print(f"✅ {name} integration created successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize {name} integration: {e}")
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Initialize integrations data in the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--force', action='store_true',
                       help='Force overwrite existing integrations')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--integration', type=str,
                       help='Initialize specific integration only (jira, github, aha, azdo)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.debug)
    
    print("🔧 ETL Service - Integration Initialization Tool")
    print("=" * 60)
    print("This tool initializes configured integrations in the database")
    print("with encrypted tokens for secure storage.")
    print()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()
    
    # Get configured integrations
    try:
        configured_integrations = get_configured_integrations()
        
        if not configured_integrations:
            print("❌ No integrations are configured in the environment")
            print("💡 Make sure your .env file contains the required settings")
            return 1
        
        print(f"📋 Found {len(configured_integrations)} configured integrations:")
        for integration in configured_integrations:
            status = "Required" if integration['required'] else "Optional"
            print(f"   • {integration['name']} ({status})")
        print()
        
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return 1
    
    # Filter by specific integration if requested
    if args.integration:
        integration_name_map = {
            'jira': 'Jira',
            'github': 'GitHub', 
            'aha': 'Aha!',
            'azdo': 'Azure DevOps'
        }
        
        target_name = integration_name_map.get(args.integration.lower())
        if not target_name:
            print(f"❌ Unknown integration: {args.integration}")
            print(f"💡 Available: {', '.join(integration_name_map.keys())}")
            return 1
        
        configured_integrations = [i for i in configured_integrations if i['name'] == target_name]
        if not configured_integrations:
            print(f"❌ {target_name} integration is not configured")
            return 1
    
    # Check existing integrations (unless dry run)
    if not args.dry_run:
        print("🔍 Checking existing integrations...")
        existing = check_existing_integrations()
        if existing:
            print(f"   Found {len(existing)} existing integrations:")
            for name, info in existing.items():
                print(f"   • {name} (ID: {info['id']})")
        else:
            print("   No existing integrations found")
        print()
    
    # Initialize integrations
    success_count = 0
    total_count = len(configured_integrations)
    
    for integration in configured_integrations:
        if initialize_integration(integration, args.force, args.dry_run):
            success_count += 1
    
    # Summary
    print()
    print("=" * 60)
    print("📊 Initialization Summary")
    print("-" * 30)
    print(f"Total integrations: {total_count}")
    print(f"Successfully processed: {success_count}")
    print(f"Failed: {total_count - success_count}")
    
    if args.dry_run:
        print()
        print("💡 This was a dry run - no changes were made")
        print("   Remove --dry-run to apply changes")
    elif success_count == total_count:
        print()
        print("🎉 All integrations initialized successfully!")
    else:
        print()
        print("⚠️  Some integrations failed to initialize")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
