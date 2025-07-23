#!/usr/bin/env python3
"""
ETL Service Jobs Testing Tool - Unified Architecture

This script provides a simplified interface for testing ETL jobs using the unified
execution architecture. It calls the same job functions used in production with
different execution modes for targeted testing.

Usage:
    python scripts/test_jobs.py                    # Interactive manual testing (default)
    python scripts/test_jobs.py --test-connection  # Test API connections
    python scripts/test_jobs.py --debug            # Enable debug logging
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directory to Python path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Import database and models
from app.core.database import get_database
from app.models.unified_models import Integration


def setup_logging(debug=False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def test_connection():
    """Test API connections for all integrations."""
    print("🔌 Testing API Connections...")
    print("=" * 50)
    
    database = get_database()
    success = True
    
    with database.get_session() as session:
        integrations = session.query(Integration).all()
        
        if not integrations:
            print("❌ No integrations found. Please run 'python scripts/reset_database.py --all' first.")
            return False
        
        for integration in integrations:
            print(f"\n🔗 Testing {integration.name} connection...")
            
            if integration.name.upper() == 'JIRA':
                success &= test_jira_connection(integration)
            elif integration.name.upper() == 'GITHUB':
                success &= test_github_connection(integration)
            elif integration.name.upper() == 'AHA!':
                success &= test_aha_connection(integration)
            elif integration.name.upper() == 'AZURE DEVOPS':
                success &= test_azdo_connection(integration)
            else:
                print(f"   ⚠️  {integration.name} connection testing not implemented")
    
    return success


def test_jira_connection(integration):
    """Test Jira API connection."""
    try:
        from app.jobs.jira import JiraAPIClient
        from app.core.config import AppConfig
        import requests

        key = AppConfig.load_key()
        jira_token = AppConfig.decrypt_token(integration.password, key)

        client = JiraAPIClient(
            username=integration.username,
            token=jira_token,
            base_url=integration.url
        )

        # Test connection by getting server info using the same method as JiraAPIClient
        response = requests.get(
            f"{integration.url}/rest/api/2/serverInfo",
            auth=(integration.username, jira_token),
            timeout=30
        )
        response.raise_for_status()

        server_info = response.json()
        print(f"   ✅ Connected to Jira: {server_info.get('serverTitle', 'Unknown')}")
        print(f"   📊 Version: {server_info.get('version', 'Unknown')}")
        return True

    except Exception as e:
        print(f"   ❌ Jira connection error: {e}")
        return False


def test_github_connection(integration):
    """Test GitHub API connection."""
    try:
        from app.jobs.github.github_client import GitHubClient
        from app.core.config import AppConfig
        
        key = AppConfig.load_key()
        github_token = AppConfig.decrypt_token(integration.password, key)
        
        client = GitHubClient(github_token)
        
        # Test connection by getting rate limit info
        response = client.session.get("https://api.github.com/rate_limit")
        response.raise_for_status()
        
        rate_info = response.json()
        core_limit = rate_info['resources']['core']
        
        print(f"   ✅ Connected to GitHub API")
        print(f"   📊 Rate limit: {core_limit['remaining']}/{core_limit['limit']}")
        return True
        
    except Exception as e:
        print(f"   ❌ GitHub connection error: {e}")
        return False


def test_aha_connection(integration):
    """Test Aha! API connection."""
    try:
        from app.core.config import AppConfig
        import requests

        key = AppConfig.load_key()
        aha_token = AppConfig.decrypt_token(integration.password, key)

        # Test connection by getting account info
        response = requests.get(
            f"{integration.url}/api/v1/account",
            headers={
                'Authorization': f'Bearer {aha_token}',
                'Accept': 'application/json'
            },
            timeout=30
        )
        response.raise_for_status()

        account_info = response.json()
        print(f"   ✅ Connected to Aha!: {account_info.get('account', {}).get('name', 'Unknown')}")
        print(f"   📊 URL: {integration.url}")
        return True

    except Exception as e:
        print(f"   ❌ Aha! connection error: {e}")
        return False


def test_azdo_connection(integration):
    """Test Azure DevOps API connection."""
    try:
        from app.core.config import AppConfig
        import requests
        import base64

        key = AppConfig.load_key()
        azdo_token = AppConfig.decrypt_token(integration.password, key)

        # Azure DevOps uses Basic auth with empty username and PAT as password
        auth_string = base64.b64encode(f":{azdo_token}".encode()).decode()

        # Test connection by getting projects
        response = requests.get(
            f"{integration.url}/_apis/projects?api-version=6.0",
            headers={
                'Authorization': f'Basic {auth_string}',
                'Accept': 'application/json'
            },
            timeout=30
        )
        response.raise_for_status()

        projects_info = response.json()
        project_count = projects_info.get('count', 0)
        print(f"   ✅ Connected to Azure DevOps")
        print(f"   📊 Projects accessible: {project_count}")
        return True

    except Exception as e:
        print(f"   ❌ Azure DevOps connection error: {e}")
        return False


def manual_debug_unified():
    """
    Unified manual debugging interface using the new execution modes.
    Calls main job functions with different execution parameters.
    """
    print("\n" + "=" * 60)
    print("🔧 ETL SERVICE - UNIFIED MANUAL TESTING")
    print("=" * 60)
    print("This tool uses the same job functions as production")
    print("with different execution modes for targeted testing.")
    print("=" * 60)

    database = get_database()
    
    with database.get_session() as session:
        # Get integrations
        integrations = session.query(Integration).all()
        integration_lookup = {integration.name.upper(): integration for integration in integrations}
        
        if not integrations:
            print("❌ No integrations found. Please run 'python scripts/reset_database.py --all' first.")
            return
        
        while True:
            print("\n📋 AVAILABLE TEST OPTIONS:")
            print("=" * 40)
            
            # Jira options
            if 'JIRA' in integration_lookup:
                print("🎫 JIRA JOBS:")
                print("   1. Extract issue types and projects (ISSUETYPES mode)")
                print("   2. Extract statuses and project links (STATUSES mode)")
                print("   3. Extract issues, changelogs, dev_status (ISSUES mode)")
                print("   4. Execute custom JQL query (CUSTOM_QUERY mode)")
                print("   5. Full Jira extraction (ALL mode)")
                print()

            # GitHub options
            if 'GITHUB' in integration_lookup:
                print("🐙 GITHUB JOBS:")
                print("   6. Discover repositories only (REPOSITORIES mode)")
                print("   7. Extract pull requests only (PULL_REQUESTS mode)")
                print("   8. Extract single repository PRs (SINGLE_REPO mode)")
                print("   9. Full GitHub extraction (ALL mode)")
                print()
            
            print("🔧 UTILITIES:")
            print("   10. Test API connections")
            print("   0. Exit")
            print("=" * 40)
            
            try:
                choice = input("\n👉 Select option (0-10): ").strip()
                
                if choice == '0':
                    print("👋 Goodbye!")
                    break
                elif choice == '10':
                    test_connection()
                    continue
                elif choice in ['1', '2', '3', '4', '5'] and 'JIRA' in integration_lookup:
                    execute_jira_test_mode(session, integration_lookup['JIRA'], choice)
                elif choice in ['6', '7', '8', '9'] and 'GITHUB' in integration_lookup:
                    execute_github_test_mode(session, integration_lookup['GITHUB'], choice)
                else:
                    print("❌ Invalid choice or integration not available.")
                    
            except KeyboardInterrupt:
                print("\n👋 Interrupted by user. Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()


def execute_jira_test_mode(session, jira_integration, choice):
    """Execute Jira job with specific execution mode."""
    try:
        from app.jobs.jira.jira_job import run_jira_sync, JiraExecutionMode
        from app.models.unified_models import JobSchedule
        
        print(f"\n🎫 Executing Jira test mode {choice}...")
        
        # Create or get job schedule
        job_schedule = session.query(JobSchedule).filter(JobSchedule.job_name == 'jira_sync').first()
        if not job_schedule:
            job_schedule = JobSchedule(job_name='jira_sync', status='PENDING')
            session.add(job_schedule)
            session.commit()
        
        # Set execution parameters based on choice
        if choice == '1':
            mode = JiraExecutionMode.ISSUETYPES
            custom_query = None
            print("📊 Mode: ISSUETYPES - Extracting issue types and projects")
        elif choice == '2':
            mode = JiraExecutionMode.STATUSES
            custom_query = None
            print("📊 Mode: STATUSES - Extracting statuses and project links")
        elif choice == '3':
            mode = JiraExecutionMode.ISSUES
            custom_query = None
            print("📊 Mode: ISSUES - Extracting issues, changelogs, dev_status")
        elif choice == '4':
            mode = JiraExecutionMode.CUSTOM_QUERY
            print("📊 Mode: CUSTOM_QUERY - Execute custom JQL query")
            custom_query = input("Enter JQL query: ").strip()
            if not custom_query:
                print("❌ No query provided. Aborting.")
                return
            print(f"🔍 Query: {custom_query}")
        elif choice == '5':
            mode = JiraExecutionMode.ALL
            custom_query = None
            print("📊 Mode: ALL - Full Jira extraction (production behavior)")
        
        # Execute the job
        print("🚀 Starting Jira job execution...")
        import asyncio
        asyncio.run(run_jira_sync(
            session, job_schedule,
            execution_mode=mode,
            custom_query=custom_query,
            update_sync_timestamp=False,  # Don't update timestamps in test mode
            update_job_schedule=False     # Don't update job schedule in test mode
        ))
        
        print("✅ Jira job execution completed!")
        
    except Exception as e:
        print(f"❌ Error executing Jira test: {e}")
        import traceback
        traceback.print_exc()


def execute_github_test_mode(session, github_integration, choice):
    """Execute GitHub job with specific execution mode."""
    try:
        from app.jobs.github.github_job import run_github_sync, GitHubExecutionMode
        from app.models.unified_models import JobSchedule
        
        print(f"\n🐙 Executing GitHub test mode {choice}...")
        
        # Create or get job schedule
        job_schedule = session.query(JobSchedule).filter(JobSchedule.job_name == 'github_sync').first()
        if not job_schedule:
            job_schedule = JobSchedule(job_name='github_sync', status='PENDING')
            session.add(job_schedule)
            session.commit()
        
        # Set execution parameters based on choice
        target_repository = None
        
        if choice == '6':
            mode = GitHubExecutionMode.REPOSITORIES
            print("📊 Mode: REPOSITORIES - Repository discovery only")
        elif choice == '7':
            mode = GitHubExecutionMode.PULL_REQUESTS
            print("📊 Mode: PULL_REQUESTS - Extract pull requests for all repos")
        elif choice == '8':
            mode = GitHubExecutionMode.SINGLE_REPO
            print("📊 Mode: SINGLE_REPO - Extract PRs from specific repository")
            target_repository = input("Enter repository (format: owner/repo): ").strip()
            if not target_repository or '/' not in target_repository:
                print("❌ Invalid repository format. Use 'owner/repo'. Aborting.")
                return
            print(f"🎯 Target Repository: {target_repository}")
        elif choice == '9':
            mode = GitHubExecutionMode.ALL
            print("📊 Mode: ALL - Full GitHub extraction (production behavior)")
        
        # Execute the job
        print("🚀 Starting GitHub job execution...")
        import asyncio
        asyncio.run(run_github_sync(
            session, job_schedule,
            execution_mode=mode,
            target_repository=target_repository,
            update_sync_timestamp=False,  # Don't update timestamps in test mode
            update_job_schedule=False     # Don't update job schedule in test mode
        ))
        
        print("✅ GitHub job execution completed!")
        
    except Exception as e:
        print(f"❌ Error executing GitHub test: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point - defaults to manual mode."""
    parser = argparse.ArgumentParser(
        description="ETL Service Jobs Testing Tool - Unified Architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/test_jobs.py                    # Interactive manual testing (default)
    python scripts/test_jobs.py --test-connection  # Test API connections
    python scripts/test_jobs.py --debug            # Enable debug logging
        """
    )

    parser.add_argument('--test-connection', action='store_true',
                       help='Test API connections for all integrations')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')

    args = parser.parse_args()

    # Default to manual mode if no arguments provided
    if not any(vars(args).values()):
        args.manual = True
    else:
        args.manual = False

    # Setup logging if debug enabled
    if args.debug:
        setup_logging(debug=True)

    success = True

    try:
        if args.test_connection:
            success &= test_connection()
        elif args.manual:
            manual_debug_unified()  # Use new unified manual debug
        
        if success and not args.manual:
            print("\n🎉 All operations completed successfully!")
        elif not success:
            print("\n⚠️  Some operations failed. Check the output above.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n👋 Interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
