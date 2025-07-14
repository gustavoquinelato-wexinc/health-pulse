#!/usr/bin/env python3
"""
ETL Service - Jobs Testing & Debugging Tool

This script helps you test connections and debug job execution for all integrations.

Usage:
    python utils/test_jobs.py [options]

Examples:
    # 🔗 CONNECTION TESTING:
    python utils/test_jobs.py --test-connection # Test API connections
    python utils/test_jobs.py --test-scheduler  # Test scheduler configuration

    # 🐛 JOB DEBUGGING:
    python utils/test_jobs.py --manual          # Interactive manual debugging
    python utils/test_jobs.py --auto            # Full job with monitoring
    python utils/test_jobs.py --auto --debug    # Full job with verbose logging
    python utils/test_jobs.py --breakpoint      # Run with Python debugger breakpoint
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
    """Setup logging configuration."""
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
                    print("   8. Run Full GitHub Extraction")

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
            print("\n🔄 Running Full GitHub Extraction...")
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


# GitHub Manual Operation Functions

def extract_repositories_manual(session, github_integration, github_token, logger):
    """Manually extract repositories using GitHub Search API."""
    try:
        from app.jobs.github import GitHubClient
        from app.models.unified_models import Repository
        from app.jobs.github.github_graphql_processor import GitHubGraphQLProcessor

        from datetime import datetime
        import os

        print("🔍 Starting repository extraction...")

        # Setup GitHub client
        github_client = GitHubClient(github_token)

        # Get organization from environment
        org = os.getenv('GITHUB_ORG', 'wexinc')
        name_filter = os.getenv('GITHUB_REPO_FILTER', 'health-')

        print(f"📋 Searching for repositories in org: {org}")
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
        repos = github_client.search_repositories(org, start_date, end_date, name_filter)
        print(f"📁 Found {len(repos)} repositories")

        if not repos:
            print("⚠️  No repositories found")
            return

        # Process repositories using bulk operations
        processor = GitHubGraphQLProcessor(github_integration, None)

        # Get existing repositories to avoid duplicates
        existing_repos = {
            repo.external_id: repo for repo in session.query(Repository).filter(
                Repository.client_id == github_integration.client_id
            ).all()
        }

        repos_to_insert = []
        repos_skipped = 0

        print(f"🔄 Processing {len(repos)} repositories...")
        for repo_index, repo_data in enumerate(repos, 1):
            try:
                print(f"📁 Processing repository {repo_index}/{len(repos)}: {repo_data.get('full_name', 'unknown')}")

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
        graphql_client = GitHubGraphQLClient(github_token, rate_limit_threshold=500)

        # Create a mock job schedule for testing
        mock_job_schedule = type('MockJobSchedule', (), {
            'is_recovery_run': lambda: False,
            'get_checkpoint_state': lambda: {}
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

                if result['success']:
                    prs_processed = result['prs_processed']
                    total_prs_processed += prs_processed

                    # Commit the data for this repository
                    session.commit()
                    print(f"✅ Processed {prs_processed} PRs for {owner}/{repo_name} - Data committed to database")
                else:
                    print(f"❌ Failed to process PRs for {owner}/{repo_name}: {result['error']}")

                # Check rate limit and warn but continue
                if graphql_client.should_stop_for_rate_limit():
                    print("⚠️  Rate limit threshold reached, but continuing extraction")

            except Exception as e:
                print(f"❌ Error processing repository {repository.full_name}: {e}")
                continue

        print(f"\n🎉 Pull request extraction completed!")
        print(f"   • Total PRs processed: {total_prs_processed}")
        print(f"   • Repositories processed: {repo_index}")

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
        graphql_client = GitHubGraphQLClient(github_token, rate_limit_threshold=500)

        # Create a mock job schedule for testing
        mock_job_schedule = type('MockJobSchedule', (), {
            'is_recovery_run': lambda: False,
            'get_checkpoint_state': lambda: {}
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
                print(f"\n🎉 Pull request extraction completed!")
                print(f"   • PRs processed: {prs_processed}")
                print(f"   • Repository: {repo_full_name}")
                print(f"   • Data committed to database")
            else:
                print(f"❌ Failed to process PRs: {result['error']}")

        except ValueError:
            print(f"❌ Invalid repository name format. Expected 'owner/repo', got '{repo_full_name}'")

    except Exception as e:
        print(f"❌ Error in single repository PR extraction: {e}")
        raise


def run_full_github_extraction_manual(session, github_integration, github_token, logger):
    """Run full GitHub extraction (repositories + pull requests) manually."""
    try:
        print("🚀 Starting full GitHub extraction...")
        print("=" * 60)

        # Step 1: Extract repositories
        print("\n📋 Step 1: Extracting repositories...")
        extract_repositories_manual(session, github_integration, github_token, logger)

        # Step 2: Extract pull requests for all repositories
        print("\n📋 Step 2: Extracting pull requests...")
        extract_all_pull_requests_manual(session, github_integration, github_token, logger)

        print("\n🎉 Full GitHub extraction completed!")
        print("=" * 60)

        # Show summary
        from app.models.unified_models import Repository, PullRequest

        repo_count = session.query(Repository).filter(
            Repository.client_id == github_integration.client_id,
            Repository.active == True
        ).count()

        pr_count = session.query(PullRequest).join(Repository).filter(
            Repository.client_id == github_integration.client_id,
            Repository.active == True
        ).count()

        print(f"📊 Final Summary:")
        print(f"   • Total repositories: {repo_count}")
        print(f"   • Total pull requests: {pr_count}")

    except Exception as e:
        print(f"❌ Error in full GitHub extraction: {e}")
        raise

if __name__ == "__main__":
    main()
