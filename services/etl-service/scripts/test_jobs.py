#!/usr/bin/env python3
"""
ETL Service - Jobs Testing & Debugging Tool

This script helps you test connections and debug job execution for all integrations.

Usage:
    python scripts/test_jobs.py [options]

Examples:
    # 🔗 CONNECTION TESTING:
    python scripts/test_jobs.py --test-connection # Test API connections
    python scripts/test_jobs.py --test-scheduler  # Test scheduler configuration

    # 🐛 JOB DEBUGGING:
    python scripts/test_jobs.py --manual          # Interactive manual debugging
    python scripts/test_jobs.py --auto            # Full job with monitoring
    python scripts/test_jobs.py --auto --debug    # Full job with verbose logging
    python scripts/test_jobs.py --breakpoint      # Run with Python debugger breakpoint
"""

import sys
import argparse
import logging
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to Python path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Setup logging early to suppress SQLAlchemy logs before any imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Disable SQLAlchemy logging for cleaner output
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)

# Override DEBUG setting to disable SQLAlchemy echo for test_jobs
import os
os.environ['DEBUG'] = 'false'

# Fix Unicode encoding issues on Windows console
if sys.platform == "win32":
    try:
        # Try to set console to UTF-8 encoding
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        # If that fails, we'll handle it in the logging configuration
        pass

def setup_logging(debug=False):
    """Setup logging configuration using the main app's colored logging."""
    try:
        # Import and use the main app's colored logging configuration
        from app.core.logging_config import setup_logging as app_setup_logging
        app_setup_logging(force_reconfigure=True)  # Force reconfiguration
        print("✅ Using colored logging configuration")
    except ImportError as e:
        # Fallback to basic logging if app modules aren't available
        level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        print(f"⚠️  Using basic logging configuration (colored logging not available: {e})")
    except Exception as e:
        print(f"⚠️  Error setting up colored logging: {e}")
        # Fallback to basic logging
        level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )

    # Disable SQLAlchemy logging for cleaner output
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)

def test_connection():
    """Test API connections for all integrations."""
    print("🔗 Testing API Connections...")
    print("=" * 60)
    
    try:
        from app.core.database import get_database
        from app.models.unified_models import Integration
        
        database = get_database()
        
        with database.get_session_context() as session:
            integrations = session.query(Integration).filter(Integration.active == True).all()
            
            if not integrations:
                print("❌ No active integrations found in database")
                return False
            
            print(f"📊 Found {len(integrations)} active integrations")
            
            for integration in integrations:
                print(f"\n🔍 Testing {integration.name} integration...")
                
                if integration.name.lower() == 'jira':
                    success = test_jira_connection(integration)
                elif integration.name.lower() == 'github':
                    success = test_github_connection(integration)
                elif integration.name.lower() == 'aha!':
                    success = test_aha_connection(integration)
                elif integration.name.lower() == 'azure devops':
                    success = test_azure_devops_connection(integration)
                else:
                    print(f"   ⚠️  Unknown integration type: {integration.name}")
                    continue
                
                if success:
                    print(f"   ✅ {integration.name} connection successful")
                else:
                    print(f"   ❌ {integration.name} connection failed")
            
            return True
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def test_jira_connection(integration):
    """Test Jira API connection."""
    try:
        from app.jobs.jira import JiraAPIClient
        from app.core.config import AppConfig

        # Decrypt the token and extract connection details
        key = AppConfig.load_key()
        decrypted_token = AppConfig.decrypt_token(integration.password, key)
        username = integration.username
        base_url = integration.url

        client = JiraAPIClient(username, decrypted_token, base_url)

        # Test basic API call by getting projects
        projects = client.get_projects(max_results=1)
        if projects is not None:
            print(f"   👤 Connected successfully - found {len(projects)} project(s)")
            return True
        else:
            print("   ❌ Failed to get projects")
            return False

    except Exception as e:
        print(f"   ❌ Jira connection error: {e}")
        return False

def test_github_connection(integration):
    """Test GitHub API connection."""
    try:
        from app.jobs.github import GitHubClient
        from app.core.config import get_settings
        
        settings = get_settings()
        github_token = getattr(settings, 'github_token', None)
        
        if not github_token:
            print("   ❌ GitHub token not configured")
            return False
        
        client = GitHubClient(github_token)
        
        # Test basic API call
        response = client._make_request("user")
        if response and 'login' in response:
            print(f"   👤 Connected as: {response.get('login', 'Unknown')}")
            return True
        else:
            print("   ❌ Failed to get user info")
            return False
            
    except Exception as e:
        print(f"   ❌ GitHub connection error: {e}")
        return False

def test_aha_connection(integration):
    """Test Aha! API connection."""
    print("   ⚠️  Aha! connection testing not yet implemented")
    return True

def test_azure_devops_connection(integration):
    """Test Azure DevOps API connection."""
    print("   ⚠️  Azure DevOps connection testing not yet implemented")
    return True

def test_scheduler():
    """Test scheduler configuration."""
    print("🕐 Testing Scheduler Configuration...")
    print("=" * 60)

    try:
        from app.main import get_scheduler

        scheduler = get_scheduler()

        if not scheduler:
            print("⚠️  Scheduler not available (APScheduler not installed)")
            return True

        print("✅ Scheduler imported successfully")
        print(f"📊 Scheduler state: {'Running' if scheduler.running else 'Stopped'}")

        # List configured jobs
        jobs = scheduler.get_jobs()
        print(f"📋 Configured jobs: {len(jobs)}")

        for job in jobs:
            print(f"   • {job.id}: {job.name}")
            print(f"     Next run: {job.next_run_time}")

        return True

    except Exception as e:
        print(f"❌ Scheduler test failed: {e}")
        return False

def manual_debug():
    """Interactive manual debugging mode with unified menu."""
    print("🐛 Manual Debugging Mode")
    print("=" * 60)

    # Setup colored logging BEFORE importing any app modules
    setup_logging(debug=True)

    try:
        from app.core.database import get_database
        from app.models.unified_models import Integration

        database = get_database()

        # Get available integrations once (outside the loop to avoid logs)
        with database.get_session_context() as session:
            integrations = session.query(Integration).filter(Integration.active == True).all()

            if not integrations:
                print("❌ No active integrations found")
                return

            # Create integration lookup with just the data we need (not the ORM objects)
            integration_data = []
            for integration in integrations:
                integration_data.append({
                    'id': integration.id,
                    'name': integration.name,
                    'url': integration.url,
                    'username': integration.username,
                    'password': integration.password,
                    'client_id': integration.client_id
                })

        # Create integration lookup from the data
        integration_lookup = {data['name'].lower(): data for data in integration_data}

        while True:
            try:
                print("\n� Available ETL Operations:")
                print("=" * 50)

                # Jira operations
                if 'jira' in integration_lookup:
                    print("📊 Jira Operations:")
                    print("   1. Extract Projects and Issue Types (Combined)")
                    print("   2. Extract Projects and Statuses (Combined)")
                    print("   3. Extract Issues and Changelogs (Combined)")
                    print("   4. Run Full Jira Job")

                # GitHub operations
                if 'github' in integration_lookup:
                    print("\n🐙 GitHub Operations:")
                    print("   5. Extract Repositories")
                    print("   6. Extract Pull Requests (All Repositories)")
                    print("   7. Extract Pull Requests (Single Repository)")
                    print("   8. Run Full GitHub Job (Real Job Simulation)")

                """
                # Other integrations
                if 'aha!' in integration_lookup:
                    print("\n🎯 Aha! Operations:")
                    print("   9. Run Aha! Extraction (Not Implemented)")

                if 'azure devops' in integration_lookup:
                    print("\n🔷 Azure DevOps Operations:")
                    print("   10. Run Azure DevOps Extraction (Not Implemented)")
                """
                print("\n   q. Quit")

                choice = input(f"\nSelect operation (1-10) or 'q' to quit: ").strip()

                if choice.lower() == 'q':
                    break

                # Execute the selected operation
                if choice in ['1', '2', '3', '4'] and 'jira' in integration_lookup:
                    with database.get_session_context() as session:
                        # Get fresh integration object from the session
                        jira_integration = session.query(Integration).filter(Integration.id == integration_lookup['jira']['id']).first()
                        run_jira_operation(session, jira_integration, choice)
                elif choice in ['5', '6', '7', '8'] and 'github' in integration_lookup:
                    with database.get_session_context() as session:
                        # Get fresh integration object from the session
                        github_integration = session.query(Integration).filter(Integration.id == integration_lookup['github']['id']).first()
                        run_github_operation(session, github_integration, choice)
                elif choice == '9' and 'aha!' in integration_lookup:
                    print("⚠️  Aha! extraction not yet implemented")
                elif choice == '10' and 'azure devops' in integration_lookup:
                    print("⚠️  Azure DevOps extraction not yet implemented")
                else:
                    print("❌ Please enter a valid operation number")

            except ValueError:
                print("❌ Please enter a valid number")
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

    except Exception as e:
        print(f"❌ Manual debug failed: {e}")

def run_jira_operation(session, jira_integration, choice):
    """Run a specific Jira operation."""
    try:
        from app.jobs.jira import JiraAPIClient
        from app.jobs.jira.jira_extractors import extract_projects_and_issuetypes, extract_projects_and_statuses, extract_work_items_and_changelogs
        from app.core.config import AppConfig
        from app.core.logging_config import JobLogger


        # Setup
        key = AppConfig.load_key()
        jira_token = AppConfig.decrypt_token(jira_integration.password, key)
        jira_client = JiraAPIClient(
            username=jira_integration.username,
            token=jira_token,
            base_url=jira_integration.url
        )
        logger = JobLogger("manual_debug")

        if choice == '1':
            print("\n🔄 Extracting Projects and Issue Types...")
            result = extract_projects_and_issuetypes(session, jira_client, jira_integration, logger)
            print(f"✅ Result: {result['projects_processed']} projects processed")
            print(f"✅ Result: {result['issuetypes_processed']} issue types processed")

        elif choice == '2':
            print("\n🔄 Extracting Projects and Statuses...")
            result = extract_projects_and_statuses(session, jira_client, jira_integration, logger)
            print(f"✅ Result: {result['statuses_processed']} statuses processed")
            print(f"✅ Result: {result['relationships_processed']} project-status relationships processed")

        elif choice == '3':
            print("\n🔄 Extracting Issues and Changelogs...")

            # Clear staging table before extraction to avoid duplicates
            from app.models.unified_models import JiraDevDetailsStaging, Issue
            staging_count = session.query(JiraDevDetailsStaging).join(Issue).filter(
                Issue.integration_id == jira_integration.id
            ).count()

            if staging_count > 0:
                print(f"🧹 Clearing {staging_count} existing dev_status staging records...")
                session.query(JiraDevDetailsStaging).filter(
                    JiraDevDetailsStaging.issue_id.in_(
                        session.query(Issue.id).filter(Issue.client_id == jira_integration.client_id)
                    )
                ).delete(synchronize_session=False)
                session.commit()
                print(f"✅ Cleared existing staging records")

            result = extract_work_items_and_changelogs(session, jira_client, jira_integration, logger)
            print(f"✅ Result: {result['issues_processed']} issues processed")
            print(f"✅ Result: {result['changelogs_processed']} changelogs processed")
            print(f"✅ Result: {result.get('dev_status_staged', 0)} dev_status records staged")
            print(f"📊 Issue keys: {len(result['issue_keys'])} keys collected for development data processing")

        elif choice == '4':
            print("\n🔄 Running Full Jira Job via New Orchestration...")
            from app.jobs.orchestrator import trigger_jira_sync
            import asyncio
            result = asyncio.run(trigger_jira_sync())
            print(f"✅ Full job result: {result}")

    except Exception as e:
        print(f"❌ Error in Jira operation: {e}")
        import traceback
        traceback.print_exc()


def run_github_operation(session, github_integration, choice):
    """Run a specific GitHub operation."""
    try:
        from app.core.config import AppConfig
        from app.core.logging_config import JobLogger

        # Setup
        key = AppConfig.load_key()
        github_token = AppConfig.decrypt_token(github_integration.password, key)
        logger = JobLogger("manual_debug")

        if choice == '5':
            print("\n🔄 Extracting Repositories...")
            extract_repositories_manual(session, github_integration, github_token, logger)

        elif choice == '6':
            print("\n🔄 Extracting Pull Requests (All Repositories)...")
            extract_all_pull_requests_manual(session, github_integration, github_token, logger)

        elif choice == '7':
            print("\n🔄 Extracting Pull Requests (Single Repository)...")
            repo_full_name = input("Enter repository full name (owner/repo): ").strip()
            if repo_full_name:
                extract_single_repo_pull_requests_manual(session, github_integration, github_token, repo_full_name, logger)
            else:
                print("❌ Repository name required")

        elif choice == '8':
            print("\n� Running Full GitHub Job (Real Job Simulation)...")
            run_full_github_extraction_manual(session, github_integration, github_token, logger)

    except Exception as e:
        print(f"❌ Error in GitHub operation: {e}")
        import traceback
        traceback.print_exc()

# Old run_jira_debug function removed - replaced by run_jira_operation in unified menu

# Old run_github_debug function removed - replaced by run_github_operation in unified menu

def auto_debug(debug=False):
    """Automatic debugging mode - runs full job with monitoring."""
    print("🤖 Automatic Debugging Mode")
    print("=" * 60)

    setup_logging(debug)

    try:
        from app.jobs.orchestrator import trigger_jira_sync
        import asyncio

        print("🚀 Starting full job execution via new orchestration...")
        start_time = datetime.now()

        result = asyncio.run(trigger_jira_sync())

        end_time = datetime.now()
        duration = end_time - start_time

        print(f"\n✅ Job completed successfully!")
        print(f"⏱️  Duration: {duration}")
        print(f"📊 Results:")
        print(json.dumps(result, indent=2, default=str))

        return True

    except Exception as e:
        print(f"❌ Auto debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def breakpoint_debug():
    """Run with Python debugger breakpoint."""
    print("🔍 Breakpoint Debugging Mode")
    print("=" * 60)
    print("💡 Python debugger will start. Use 'c' to continue, 'n' for next line, 'q' to quit.")

    try:
        breakpoint()  # Python 3.7+ built-in debugger

        from app.jobs.orchestrator import trigger_jira_sync
        import asyncio
        result = asyncio.run(trigger_jira_sync())

        print("✅ Breakpoint debug completed!")
        print(f"📊 Result: {result}")
        return True

    except Exception as e:
        print(f"❌ Breakpoint debug failed: {e}")
        return False

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ETL Service Jobs Testing & Debugging Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python utils/test_jobs.py --test-connection    # Test API connections
    python utils/test_jobs.py --manual             # Interactive debugging
    python utils/test_jobs.py --auto --debug       # Full job with verbose logging
        """
    )

    parser.add_argument('--test-connection', action='store_true',
                       help='Test API connections for all integrations')
    parser.add_argument('--test-scheduler', action='store_true',
                       help='Test scheduler configuration')
    parser.add_argument('--manual', action='store_true',
                       help='Interactive manual debugging mode')
    parser.add_argument('--auto', action='store_true',
                       help='Automatic debugging mode (full job)')
    parser.add_argument('--breakpoint', action='store_true',
                       help='Run with Python debugger breakpoint')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    parser.add_argument('--check-checkpoint', action='store_true',
                       help='Check checkpoint data in database')

    args = parser.parse_args()

    # If no arguments provided, show help
    if not any(vars(args).values()):
        parser.print_help()
        return

    success = True

    try:
        if args.test_connection:
            success &= test_connection()

        if args.test_scheduler:
            success &= test_scheduler()

        if args.manual:
            manual_debug()

        if args.auto:
            success &= auto_debug(args.debug)

        if args.breakpoint:
            success &= breakpoint_debug()

        if args.check_checkpoint:
            check_checkpoint_data()

        if success:
            print("\n🎉 All operations completed successfully!")
        else:
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


def check_checkpoint_data():
    """Check the current checkpoint data in the database."""
    try:
        # Setup environment and imports
        import sys
        import os
        sys.path.insert(0, os.path.abspath('.'))

        from app.core.database import get_database
        from app.models.unified_models import JobSchedule
        import json

        database = get_database()
        with database.get_session_context() as session:
            github_job = session.query(JobSchedule).filter_by(job_name='github_sync').first()

            if github_job:
                print('=== GITHUB JOB CHECKPOINT DATA ===')
                print(f'Job Status: {github_job.status}')
                print(f'Error Message: {github_job.error_message}')
                print(f'Retry Count: {github_job.retry_count}')
                print(f'Last Repo Sync Checkpoint: {github_job.last_repo_sync_checkpoint}')
                print(f'Last PR Cursor: {github_job.last_pr_cursor}')
                print(f'Current PR Node ID: {github_job.current_pr_node_id}')
                print(f'Last Commit Cursor: {github_job.last_commit_cursor}')
                print(f'Last Review Cursor: {github_job.last_review_cursor}')
                print(f'Last Comment Cursor: {github_job.last_comment_cursor}')
                print(f'Last Review Thread Cursor: {github_job.last_review_thread_cursor}')

                print('\n=== REPO PROCESSING QUEUE ===')
                if github_job.repo_processing_queue:
                    queue = json.loads(github_job.repo_processing_queue)
                    print(f'Total repositories in queue: {len(queue)}')

                    finished_repos = [repo for repo in queue if repo.get("finished", False)]
                    pending_repos = [repo for repo in queue if not repo.get("finished", False)]

                    print(f'Finished repositories: {len(finished_repos)}')
                    print(f'Pending repositories: {len(pending_repos)}')

                    print('\nFirst 5 finished repositories:')
                    for repo in finished_repos[:5]:
                        print(f'  - {repo.get("full_name", "N/A")} (finished: {repo.get("finished", False)})')

                    print('\nFirst 5 pending repositories:')
                    for repo in pending_repos[:5]:
                        print(f'  - {repo.get("full_name", "N/A")} (finished: {repo.get("finished", False)})')
                else:
                    print('No repo processing queue found')

            else:
                print('No GitHub job found in database')

    except Exception as e:
        print(f"Error checking checkpoint data: {e}")


# GitHub Manual Operation Functions

def extract_repositories_manual(session, github_integration, github_token, logger):
    """Manually extract repositories combining GitHub Search API and Jira dev_status data."""
    try:
        from app.jobs.github import GitHubClient
        from app.models.unified_models import Repository, JiraDevDetailsStaging
        from app.jobs.github.github_graphql_processor import GitHubGraphQLProcessor

        from datetime import datetime
        import os

        print("🔍 Starting repository extraction...")
        print("📋 Combining repositories from:")
        print("   • GitHub Search API (with 'health-' filter)")
        print("   • Jira dev_status staging data")

        # Setup GitHub client
        github_client = GitHubClient(github_token)

        # Get organization from environment
        org = os.getenv('GITHUB_ORG', 'wexinc')
        name_filter = os.getenv('GITHUB_REPO_FILTER', 'health-')

        # Step 1: Get repositories from Jira dev_status staging data
        print("\n🔍 Step 1: Extracting repositories from Jira dev_status staging data...")

        staged_data = session.query(JiraDevDetailsStaging).filter(
            JiraDevDetailsStaging.processed == False
        ).all()

        print(f"📋 Found {len(staged_data)} staged dev_status items")

        repo_names_from_jira = set()
        for staging_record in staged_data:
            dev_data = staging_record.get_dev_status_data()
            detail = dev_data.get('detail', [])
            for detail_item in detail:
                pull_requests = detail_item.get('pullRequests', [])
                for pr_data in pull_requests:
                    repo_name = pr_data.get('repositoryName')
                    if repo_name:
                        repo_names_from_jira.add(repo_name)

        print(f"📁 Found {len(repo_names_from_jira)} unique repositories in Jira dev_status data")
        if repo_names_from_jira:
            print(f"   • Repository names: {', '.join(sorted(repo_names_from_jira))}")

        # Step 2: Get repositories from GitHub Search API
        print(f"\n🔍 Step 2: Searching GitHub API for repositories in org: {org}")
        if name_filter:
            print(f"📋 Filtering by name: {name_filter}")

        # Use integration's last_sync_at as start date, today as end date
        # Ensure we don't use dates that are too old (GitHub Search API has limits)
        if github_integration.last_sync_at and github_integration.last_sync_at.year >= 2020:
            start_date = github_integration.last_sync_at.strftime('%Y-%m-%d')
        else:
            start_date = "2024-01-01"  # Default to recent date if last_sync_at is None or too old

        end_date = datetime.today().strftime('%Y-%m-%d')

        print(f"📅 Date range: {start_date} to {end_date}")
        if github_integration.last_sync_at:
            print(f"📅 Integration last sync: {github_integration.last_sync_at}")
        else:
            print("📅 No previous sync found, using default start date")

        # Search repositories with rate limit warning
        print("Note: GitHub Search API has a rate limit of 30 requests per minute")
        repos_from_search = github_client.search_repositories(org, start_date, end_date, name_filter)
        print(f"📁 Found {len(repos_from_search)} repositories from GitHub Search API")

        # Step 3: Combine both sources
        print(f"\n🔗 Step 3: Combining repositories from both sources...")

        # Create a set of all repository names to fetch
        all_repo_names = set()

        # Add repositories from GitHub Search API
        for repo in repos_from_search:
            all_repo_names.add(repo['full_name'])

        # Add repositories from Jira dev_status (need to construct full names)
        for repo_name in repo_names_from_jira:
            # Assume they're in the same org if not already full name
            if '/' not in repo_name:
                full_name = f"{org}/{repo_name}"
            else:
                full_name = repo_name
            all_repo_names.add(full_name)

        print(f"📊 Total unique repositories to process: {len(all_repo_names)}")

        # Step 4: Fetch detailed repository data for all repositories
        print(f"\n📥 Step 4: Fetching detailed repository data...")

        all_repos = []

        # Add repos from search (already have detailed data)
        all_repos.extend(repos_from_search)

        # For repos from Jira that weren't found in search, fetch them individually
        search_repo_names = {repo['full_name'] for repo in repos_from_search}
        missing_repo_names = all_repo_names - search_repo_names

        if missing_repo_names:
            print(f"📋 Fetching {len(missing_repo_names)} additional repositories from Jira dev_status...")
            for full_name in missing_repo_names:
                try:
                    owner, repo_name = full_name.split('/', 1)
                    # Use the GitHub client's _make_request method to fetch individual repo
                    endpoint = f"repos/{owner}/{repo_name}"
                    repo_data = github_client._make_request(endpoint)
                    if repo_data:
                        all_repos.append(repo_data)
                        print(f"   ✅ Fetched: {full_name}")
                    else:
                        print(f"   ❌ Not found: {full_name}")
                except Exception as e:
                    print(f"   ❌ Error fetching {full_name}: {e}")

        print(f"📁 Total repositories to process: {len(all_repos)}")

        if not all_repos:
            print("⚠️  No repositories found from either source")
            return

        # Step 5: Process repositories using bulk operations
        print(f"\n🔄 Step 5: Processing repositories for database insertion...")
        processor = GitHubGraphQLProcessor(github_integration, None)

        # Get existing repositories to avoid duplicates
        existing_repos = {
            repo.external_id: repo for repo in session.query(Repository).filter(
                Repository.client_id == github_integration.client_id
            ).all()
        }

        repos_to_insert = []
        repos_skipped = 0

        print(f"🔄 Processing {len(all_repos)} repositories...")
        for repo_index, repo_data in enumerate(all_repos, 1):
            try:
                print(f"📁 Processing repository {repo_index}/{len(all_repos)}: {repo_data.get('full_name', 'unknown')}")

                # Check if repository already exists
                external_id = str(repo_data['id'])
                if external_id in existing_repos:
                    print(f"   ⏭️  Repository already exists (ID: {existing_repos[external_id].id})")
                    repos_skipped += 1
                    continue

                # Process repository data
                repo_processed = processor.process_repository_data(repo_data)
                if repo_processed:
                    repos_to_insert.append(repo_processed)
                    print(f"   ✅ Prepared for bulk insert")
                else:
                    print(f"   ⚠️  Failed to process repository data")

            except Exception as e:
                print(f"   ❌ Error processing repository: {e}")
                continue

        # Perform bulk insert
        if repos_to_insert:
            print(f"\n💾 Performing bulk insert of {len(repos_to_insert)} repositories...")
            session.bulk_insert_mappings(Repository, repos_to_insert)
            session.commit()
            print(f"✅ Successfully inserted {len(repos_to_insert)} repositories")
        else:
            print(f"\n⚠️  No new repositories to insert")

        print(f"\n🎉 Repository extraction completed!")
        print(f"   • Repositories processed: {len(repos_to_insert)}")
        print(f"   • Repositories skipped (already exist): {repos_skipped}")

    except Exception as e:
        print(f"❌ Error in repository extraction: {e}")
        session.rollback()
        raise


def extract_all_pull_requests_manual(session, github_integration, github_token, logger):
    """Manually extract pull requests for all repositories using GraphQL."""
    try:
        from app.jobs.github.github_graphql_client import GitHubGraphQLClient
        from app.jobs.github.github_graphql_extractor import process_repository_prs_with_graphql
        from app.models.unified_models import Repository

        print("🔄 Starting pull request extraction for all repositories...")

        # Get all repositories
        repositories = session.query(Repository).filter(
            Repository.client_id == github_integration.client_id,
            Repository.active == True
        ).all()

        if not repositories:
            print("⚠️  No repositories found. Run option 5 first to extract repositories.")
            return

        print(f"📁 Found {len(repositories)} repositories")

        # Setup GraphQL client
        from app.core.config import get_settings
        settings = get_settings()
        graphql_client = GitHubGraphQLClient(github_token, rate_limit_threshold=settings.GITHUB_RATE_LIMIT_THRESHOLD)

        # Create a mock job schedule for testing
        mock_job_schedule = type('MockJobSchedule', (), {
            'is_recovery_run': lambda self: False,
            'get_checkpoint_state': lambda self: {},
            'update_checkpoint': lambda self, checkpoint_data: None
        })()

        total_prs_processed = 0

        for repo_index, repository in enumerate(repositories, 1):  # Process all repositories
            try:
                owner, repo_name = repository.full_name.split('/', 1)
                print(f"\n🔄 Processing repository {repo_index}/{len(repositories)}: {owner}/{repo_name}")

                # Process PRs for this repository
                result = process_repository_prs_with_graphql(
                    session, graphql_client, repository, owner, repo_name,
                    github_integration, mock_job_schedule
                )

                # Check if rate limit was reached during PR processing BEFORE marking as finished
                if result.get('rate_limit_reached', False):
                    print("⚠️  Rate limit threshold reached during PR processing, stopping gracefully")
                    print(f"📊 Processed {repo_index - 1} repositories before hitting rate limit")
                    print(f"📊 Total PRs processed: {total_prs_processed}")
                    break

                if result['success']:
                    prs_processed = result['prs_processed']
                    total_prs_processed += prs_processed

                    # Commit the data for this repository
                    session.commit()
                    print(f"✅ Processed {prs_processed} PRs for {owner}/{repo_name} - Data committed to database")
                else:
                    print(f"❌ Failed to process PRs for {owner}/{repo_name}: {result['error']}")

                # Check rate limit after processing and warn but continue
                if graphql_client.should_stop_for_rate_limit():
                    print("⚠️  Rate limit threshold reached, but continuing extraction")

            except Exception as e:
                print(f"❌ Error processing repository {repository.full_name}: {e}")
                continue

        # Step 2: Link pull requests with Jira issues using staging data
        print(f"\nLinking pull requests with Jira issues...")

        from app.jobs.github.github_job import link_pull_requests_with_jira_issues
        linking_result = link_pull_requests_with_jira_issues(session, github_integration)

        if linking_result['success']:
            print(f"✅ Successfully linked {linking_result['links_created']} pull requests with Jira issues")
        else:
            print(f"⚠️  PR-Issue linking completed with warnings: {linking_result.get('error', 'Unknown error')}")
            print(f"   • Links created: {linking_result.get('links_created', 0)}")

        print(f"\n🎉 Pull request extraction and linking completed!")
        print(f"   • Total PRs processed: {total_prs_processed}")
        print(f"   • Repositories processed: {repo_index}")
        print(f"   • PR-Issue links created: {linking_result.get('links_created', 0)}")

    except Exception as e:
        print(f"❌ Error in pull request extraction: {e}")
        raise


def extract_single_repo_pull_requests_manual(session, github_integration, github_token, repo_full_name, logger):
    """Manually extract pull requests for a single repository using GraphQL."""
    try:
        from app.jobs.github.github_graphql_client import GitHubGraphQLClient
        from app.jobs.github.github_graphql_extractor import process_repository_prs_with_graphql
        from app.models.unified_models import Repository

        print(f"🔄 Starting pull request extraction for repository: {repo_full_name}")

        # Find the repository
        repository = session.query(Repository).filter(
            Repository.full_name == repo_full_name,
            Repository.client_id == github_integration.client_id,
            Repository.active == True
        ).first()

        if not repository:
            print(f"❌ Repository '{repo_full_name}' not found in database.")
            print("   Run option 5 first to extract repositories, or check the repository name.")
            return

        print(f"📁 Found repository: {repository.full_name} (ID: {repository.id})")

        # Setup GraphQL client
        from app.core.config import get_settings
        settings = get_settings()
        graphql_client = GitHubGraphQLClient(github_token, rate_limit_threshold=settings.GITHUB_RATE_LIMIT_THRESHOLD)

        # Create a mock job schedule for testing
        mock_job_schedule = type('MockJobSchedule', (), {
            'is_recovery_run': lambda self: False,
            'get_checkpoint_state': lambda self: {},
            'update_checkpoint': lambda self, checkpoint_data: None
        })()

        try:
            owner, repo_name_only = repo_full_name.split('/', 1)
            print(f"🔄 Processing PRs for {owner}/{repo_name_only}...")

            # Process PRs for this repository
            result = process_repository_prs_with_graphql(
                session, graphql_client, repository, owner, repo_name_only,
                github_integration, mock_job_schedule
            )

            if result['success']:
                prs_processed = result['prs_processed']

                # Commit the data
                session.commit()

                # Step 2: Link pull requests with Jira issues using staging data
                print(f"\nLinking pull requests with Jira issues...")

                from app.jobs.github.github_job import link_pull_requests_with_jira_issues
                linking_result = link_pull_requests_with_jira_issues(session, github_integration)

                if linking_result['success']:
                    print(f"✅ Successfully linked {linking_result['links_created']} pull requests with Jira issues")
                else:
                    print(f"⚠️  PR-Issue linking completed with warnings: {linking_result.get('error', 'Unknown error')}")
                    print(f"   • Links created: {linking_result.get('links_created', 0)}")

                print(f"\n🎉 Pull request extraction and linking completed!")
                print(f"   • PRs processed: {prs_processed}")
                print(f"   • Repository: {repo_full_name}")
                print(f"   • PR-Issue links created: {linking_result.get('links_created', 0)}")
                print(f"   • Data committed to database")
            else:
                print(f"❌ Failed to process PRs: {result['error']}")

        except ValueError:
            print(f"❌ Invalid repository name format. Expected 'owner/repo', got '{repo_full_name}'")

    except Exception as e:
        print(f"❌ Error in single repository PR extraction: {e}")
        raise


def run_full_github_extraction_manual(session, github_integration, github_token, logger=None):
    """
    Run full GitHub extraction simulating the real job behavior.

    This function:
    1. Extracts repositories and pull requests
    2. Links PRs with Jira issues using staging data
    3. On complete success: truncates staging table, updates integration last_sync_at
    4. On failure/rate limit: saves checkpoint state to JobSchedule
    5. Updates JobSchedule status appropriately
    """
    try:
        print("🚀 Starting full GitHub extraction (REAL JOB SIMULATION)...")
        print("=" * 60)
        print("This will behave like the real GitHub job:")
        print("• Extract repositories and pull requests")
        print("• Link with Jira staging data")
        print("• Update JobSchedule and Integration on success")
        print("• Truncate staging table on complete success")
        print("• Save checkpoints on failure/rate limit")
        print("=" * 60)

        # Get or create JobSchedule for github_sync
        from app.models.unified_models import JobSchedule, JiraDevDetailsStaging
        from app.core.utils import DateTimeHelper

        github_job = session.query(JobSchedule).filter(JobSchedule.job_name == 'github_sync').first()
        if not github_job:
            print("⚠️  No github_sync JobSchedule found, creating one...")
            github_job = JobSchedule(
                job_name='github_sync',
                status='PENDING',
                client_id=github_integration.client_id
            )
            session.add(github_job)
            session.commit()
            print("✅ Created github_sync JobSchedule")

        # Set job to RUNNING
        github_job.set_running()
        session.commit()
        print(f"📊 GitHub job status: {github_job.status}")

        # Step 1: Extract repositories and pull requests using the REAL GitHub job logic
        print("\n📋 Step 1: Running real GitHub job logic (repositories + pull requests)...")
        print("This includes:")
        print("   • Repository discovery from GitHub Search API ('health-' filter)")
        print("   • Repository discovery from Jira dev_status staging data")
        print("   • Fetching missing repositories individually")
        print("   • Pull request extraction using GraphQL")

        from app.jobs.github.github_job import process_github_data_with_graphql
        result = process_github_data_with_graphql(session, github_integration, github_token, github_job)

        if result['success']:
            # Step 2: Link pull requests with Jira issues using staging data
            print("\n📋 Step 2: Linking pull requests with Jira issues...")
            from app.jobs.github.github_job import link_pull_requests_with_jira_issues
            linking_result = link_pull_requests_with_jira_issues(session, github_integration)

            if linking_result['success']:
                result['pr_links_created'] = linking_result['links_created']
                print(f"✅ Successfully linked {linking_result['links_created']} pull requests with Jira issues")
            else:
                print(f"⚠️  PR-Issue linking completed with warnings: {linking_result.get('error', 'Unknown error')}")
                result['pr_links_created'] = linking_result.get('links_created', 0)

            # Check if this was a complete success (not partial or rate limited)
            is_complete_success = (
                not result.get('rate_limit_reached', False) and
                not result.get('partial_success', False)
            )

            if is_complete_success:
                # Complete Success: Clean up and finish like real job
                print("\n🎉 COMPLETE SUCCESS - Cleaning up and finishing...")

                # Clear checkpoint data
                github_job.clear_checkpoints()

                # Truncate staging table
                staging_count = session.query(JiraDevDetailsStaging).count()
                if staging_count > 0:
                    session.query(JiraDevDetailsStaging).delete()
                    print(f"🗑️  Truncated {staging_count} staging table records")
                else:
                    print("ℹ️  No staging records to truncate")

                # Update integration last_sync_at
                github_integration.last_sync_at = DateTimeHelper.now_utc()
                print(f"🕒 Updated GitHub integration last_sync_at: {github_integration.last_sync_at}")

                # Set job to FINISHED
                github_job.set_finished()
                session.commit()

                print("✅ GitHub extraction completed successfully (REAL JOB BEHAVIOR)")
                print(f"   • Repositories processed: {result['repos_processed']}")
                print(f"   • Pull requests processed: {result['prs_processed']}")
                print(f"   • PR-Issue links created: {result.get('pr_links_created', 0)}")
                print(f"   • Staging table cleared: {staging_count} records")
                print(f"   • Integration timestamp updated")
                print(f"   • Job status: FINISHED")

            else:
                # Partial Success or Rate Limit: Keep staging data, keep job PENDING
                print("\n⚠️  PARTIAL SUCCESS OR RATE LIMIT - Preserving state...")

                # Keep GitHub job as PENDING for next run
                github_job.status = 'PENDING'
                session.commit()

                print("📊 GitHub extraction partially completed (REAL JOB BEHAVIOR)")
                print(f"   • Repositories processed: {result['repos_processed']}")
                print(f"   • Pull requests processed: {result['prs_processed']}")
                print(f"   • PR-Issue links created: {result.get('pr_links_created', 0)}")
                print(f"   • Staging data preserved for next run")
                print(f"   • Job status: PENDING (will resume)")
                if result.get('rate_limit_reached'):
                    print(f"   • Rate limit reached - checkpoints saved")

        else:
            # Failure: Set job back to PENDING with checkpoint
            print("\n❌ EXTRACTION FAILED - Saving checkpoint...")
            error_msg = result.get('error', 'Unknown error')
            checkpoint_data = result.get('checkpoint_data', {})

            github_job.set_pending_with_checkpoint(
                error_msg,
                repo_checkpoint=checkpoint_data.get('repo_checkpoint'),
                repo_queue=checkpoint_data.get('repo_queue'),  # Updated parameter name
                last_pr_cursor=checkpoint_data.get('last_pr_cursor'),
                current_pr_node_id=checkpoint_data.get('current_pr_node_id'),
                last_commit_cursor=checkpoint_data.get('last_commit_cursor'),
                last_review_cursor=checkpoint_data.get('last_review_cursor'),
                last_comment_cursor=checkpoint_data.get('last_comment_cursor'),
                last_review_thread_cursor=checkpoint_data.get('last_review_thread_cursor')
            )
            session.commit()

            print(f"💾 GitHub extraction failed (REAL JOB BEHAVIOR)")
            print(f"   • Error: {error_msg}")
            print(f"   • Checkpoint data saved for recovery")
            print(f"   • Job status: PENDING (will retry)")

        # Show final summary
        print("\n" + "=" * 60)
        print("📊 FINAL SUMMARY:")

        from app.models.unified_models import Repository, PullRequest

        repo_count = session.query(Repository).filter(
            Repository.client_id == github_integration.client_id,
            Repository.active == True
        ).count()

        pr_count = session.query(PullRequest).join(Repository).filter(
            Repository.client_id == github_integration.client_id,
            Repository.active == True
        ).count()

        linked_pr_count = session.query(PullRequest).join(Repository).filter(
            Repository.client_id == github_integration.client_id,
            Repository.active == True,
            PullRequest.issue_id.isnot(None)
        ).count()

        staging_count = session.query(JiraDevDetailsStaging).count()

        print(f"   • Total repositories: {repo_count}")
        print(f"   • Total pull requests: {pr_count}")
        print(f"   • Pull requests linked to Jira issues: {linked_pr_count}")
        print(f"   • Staging records remaining: {staging_count}")
        print(f"   • Job status: {github_job.status}")
        print(f"   • Integration last_sync_at: {github_integration.last_sync_at}")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error in full GitHub extraction: {e}")

        # Set job back to PENDING on unexpected error
        try:
            github_job = session.query(JobSchedule).filter(JobSchedule.job_name == 'github_sync').first()
            if github_job:
                github_job.set_pending_with_checkpoint(str(e))
                session.commit()
                print(f"💾 Job set to PENDING due to unexpected error")
        except:
            pass

        raise

if __name__ == "__main__":
    main()
