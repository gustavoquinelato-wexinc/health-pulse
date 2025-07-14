#!/usr/bin/env python3
"""
⚠️  DEPRECATED: Test Script for GitHub Session-Based Rate Limit Management.

This script tests the OLD session management mechanism. After the GraphQL refactoring,
this approach has been replaced with cursor-based checkpoint recovery.

The new GraphQL approach uses:
- Cursor-based pagination checkpoints in JobSchedule table
- Automatic recovery without session management
- More efficient single GraphQL queries instead of multiple REST calls

For current testing, use test_jobs.py instead.

Usage:
    python utils/test_session_management.py

The script will prompt you to select one of three test scenarios:
1. Jira complete, no GitHub extraction
2. Jira complete, partial repo extraction (2 pages)
3. Jira complete, full repo extraction, partial PR extraction
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add parent directory to Python path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from app.core.database import get_database
from app.core.config import AppConfig
from app.core.logging_config import get_logger
from app.core.utils import DateTimeHelper
from app.models.unified_models import Integration, Issue, GitHubExtractionSession
# Note: GitHubSessionManager removed in GraphQL refactoring
# from app.jobs.github.session_manager import GitHubSessionManager
from app.jobs.github.github_client import GitHubClient
from app.jobs.jira.jira_client import JiraAPIClient

logger = get_logger(__name__)


class SessionManagementTester:
    """Test class for session-based rate limit management."""
    
    def __init__(self):
        self.db = get_database()
        self.session = None
        self.jira_integration = None
        self.github_integration = None
        self.jira_client = None
        self.github_client = None
        self.session_manager = None
        
    def setup(self):
        """Setup database session and integrations."""
        self.session = self.db.get_session()
        
        # Get integrations
        self.jira_integration = self.session.query(Integration).filter(
            Integration.name == "Jira"
        ).first()
        
        self.github_integration = self.session.query(Integration).filter(
            Integration.name == "GitHub"
        ).first()
        
        if not self.jira_integration:
            raise Exception("Jira integration not found")
        if not self.github_integration:
            raise Exception("GitHub integration not found")
        
        # Setup clients
        key = AppConfig.load_key()
        jira_token = AppConfig.decrypt_token(self.jira_integration.password, key)
        github_token = AppConfig.decrypt_token(self.github_integration.password, key)
        
        self.jira_client = JiraAPIClient(
            base_url=self.jira_integration.url,
            username=self.jira_integration.username,
            password=jira_token
        )
        
        self.github_client = GitHubClient(github_token, rate_limit_threshold=100)
        self.session_manager = GitHubSessionManager(self.session)
        
        print("✅ Setup completed successfully")
    
    def cleanup_existing_sessions(self):
        """Clean up any existing extraction sessions."""
        existing_sessions = self.session.query(GitHubExtractionSession).filter(
            GitHubExtractionSession.integration_id == self.github_integration.id
        ).all()
        
        for session_obj in existing_sessions:
            self.session.delete(session_obj)
        
        self.session.commit()
        print(f"🧹 Cleaned up {len(existing_sessions)} existing sessions")
    
    def extract_jira_data(self, jql_query: str, description: str) -> Dict[str, Any]:
        """Extract Jira data using the original extractors."""
        print(f"\n📊 {description}")
        print(f"JQL Query: {jql_query}")
        
        # Get issues using JQL
        jira_issues = self.jira_client.search_issues(jql_query, expand="changelog")
        print(f"Found {len(jira_issues)} issues")
        
        if not jira_issues:
            return {
                'issues_processed': 0,
                'changelogs_processed': 0,
                'dev_status_data': [],
                'issues_with_code_changed': []
            }
        
        # Process issues and changelogs using original extractors
        from app.jobs.jira.jira_extractors import extract_work_items_and_changelogs, extract_issue_dev_details
        from app.core.logging_config import JobLogger
        
        job_logger = JobLogger("test_session_management")
        
        # Extract work items and changelogs
        result = extract_work_items_and_changelogs(
            self.session, self.jira_client, self.jira_integration, job_logger
        )
        
        print(f"✅ Processed {result['issues_processed']} issues and {result['changelogs_processed']} changelogs")
        
        # Get issues with code_changed = True
        issues_with_code_changed = self.session.query(Issue).filter(
            Issue.integration_id == self.jira_integration.id,
            Issue.code_changed == True
        ).with_entities(Issue.key, Issue.external_id, Issue.id).all()
        
        issues_with_external_ids = [
            {'key': issue.key, 'external_id': issue.external_id, 'id': issue.id}
            for issue in issues_with_code_changed
        ]
        
        print(f"Found {len(issues_with_external_ids)} issues with code_changed = True")
        
        # Extract dev_status data
        dev_status_result = extract_issue_dev_details(
            self.session, self.jira_integration, self.jira_client, issues_with_external_ids
        )
        
        print(f"✅ Processed dev_status for {dev_status_result['issues_processed']} issues")
        
        return {
            'issues_processed': result['issues_processed'],
            'changelogs_processed': result['changelogs_processed'],
            'dev_status_data': dev_status_result.get('processed_dev_status_data', []),
            'issues_with_code_changed': issues_with_external_ids
        }
    
    def simulate_partial_repo_extraction(self, pages_to_process: int = 2):
        """Simulate partial repository extraction."""
        print(f"\n🔄 Simulating partial repo extraction ({pages_to_process} pages)")
        
        # Note: extract_filtered_repositories function has been removed in GraphQL refactoring
        print("⚠️  extract_filtered_repositories function no longer available after GraphQL refactoring")
        
        # Mock the GitHub client to limit pages
        original_get_repositories = self.github_client.get_repositories
        
        def limited_get_repositories(*args, **kwargs):
            repos = original_get_repositories(*args, **kwargs)
            # Simulate processing only first N pages (assume 100 repos per page)
            limited_repos = repos[:pages_to_process * 100]
            print(f"📄 Limited to {len(limited_repos)} repositories ({pages_to_process} pages)")
            return limited_repos
        
        self.github_client.get_repositories = limited_get_repositories
        
        try:
            result = extract_filtered_repositories(
                self.session, self.github_integration, self.github_client
            )
            print(f"✅ Processed {result.get('repositories_processed', 0)} repositories")
            return result
        finally:
            # Restore original method
            self.github_client.get_repositories = original_get_repositories
    
    def simulate_partial_pr_extraction(self, repos_to_process: int = 5):
        """Simulate partial pull request extraction."""
        print(f"\n🔄 Simulating partial PR extraction ({repos_to_process} repos)")
        
        # Note: extract_comprehensive_pull_requests function has been removed in GraphQL refactoring
        print("⚠️  extract_comprehensive_pull_requests function no longer available after GraphQL refactoring")
        from app.models.unified_models import Repository
        
        # Get total repositories
        total_repos = self.session.query(Repository).filter(
            Repository.client_id == self.github_integration.client_id,
            Repository.active == True
        ).count()
        
        print(f"Total repositories: {total_repos}, processing first {repos_to_process}")
        
        # Mock to process only limited repositories
        original_query = self.session.query
        
        def limited_query(model):
            if model == Repository:
                return original_query(model).limit(repos_to_process)
            return original_query(model)
        
        self.session.query = limited_query
        
        try:
            result = extract_comprehensive_pull_requests(
                self.session, self.github_integration, self.github_client
            )
            print(f"✅ Processed PRs from {result.get('repositories_processed', 0)} repositories")
            return result
        finally:
            # Restore original method
            self.session.query = original_query
    
    def create_forced_session(self, dev_status_data: List[Dict], scenario_name: str, **kwargs):
        """Create a forced extraction session to simulate interruption."""
        print(f"\n💾 Creating forced session for scenario: {scenario_name}")
        
        # Create extraction session
        extraction_session = GitHubExtractionSession(
            integration_id=self.github_integration.id,
            jira_extraction_completed_at=DateTimeHelper.now_utc(),
            jira_last_sync_used=self.jira_integration.last_sync_at,
            dev_status_data=dev_status_data,
            issues_processed=len(dev_status_data),
            **kwargs
        )
        
        self.session.add(extraction_session)
        self.session.commit()
        
        print(f"✅ Created session {extraction_session.session_id} with {len(dev_status_data)} dev_status items")
        print(f"   Repo extraction completed: {extraction_session.repo_extraction_completed}")
        print(f"   PR extraction completed: {extraction_session.pr_extraction_completed}")
        
        return extraction_session
    
    def test_scenario_1(self):
        """Test Case 1: Jira complete, no GitHub extraction."""
        print("\n" + "="*80)
        print("🧪 TEST SCENARIO 1: Jira Complete, No GitHub Extraction")
        print("="*80)
        
        # Step 1: Extract first batch of Jira data
        jira_result_1 = self.extract_jira_data(
            'project = BEX and status CHANGED DURING ("-5d","-4d")',
            "Extracting first batch of Jira data (-5d to -4d)"
        )
        
        # Step 2: Create forced session (no GitHub extraction done)
        extraction_session = self.create_forced_session(
            dev_status_data=jira_result_1['dev_status_data'],
            scenario_name="No GitHub Extraction",
            repo_extraction_completed=False,
            pr_extraction_completed=False
        )
        
        # Step 3: Extract second batch of Jira data
        jira_result_2 = self.extract_jira_data(
            'project = BEX and status CHANGED DURING ("-2d","-1d")',
            "Extracting second batch of Jira data (-2d to -1d)"
        )
        
        # Step 4: Test session-based GitHub processing
        print("\n🚀 Testing session-based GitHub processing...")
        from app.jobs.github.github_extractors import process_github_with_session_management
        
        result = process_github_with_session_management(
            self.session, self.github_integration, self.github_client,
            self.session_manager, extraction_session
        )
        
        print(f"\n✅ Scenario 1 Results:")
        print(f"   Status: {result.get('status')}")
        print(f"   Repos processed: {result.get('repos_processed', 0)}")
        print(f"   PRs processed: {result.get('pull_requests_processed', 0)}")
        print(f"   Combined PRs saved: {result.get('combined_pull_requests_saved', 0)}")
        
        return result

    def test_scenario_2(self):
        """Test Case 2: Jira complete, partial repo extraction (2 pages)."""
        print("\n" + "="*80)
        print("🧪 TEST SCENARIO 2: Jira Complete, Partial Repo Extraction")
        print("="*80)

        # Step 1: Extract first batch of Jira data
        jira_result_1 = self.extract_jira_data(
            'project = BEX and status CHANGED DURING ("-5d","-4d")',
            "Extracting first batch of Jira data (-5d to -4d)"
        )

        # Step 2: Process first 2 pages of repositories
        repo_result = self.simulate_partial_repo_extraction(pages_to_process=2)

        # Step 3: Create forced session (partial repo extraction done)
        extraction_session = self.create_forced_session(
            dev_status_data=jira_result_1['dev_status_data'],
            scenario_name="Partial Repo Extraction",
            repo_extraction_completed=True,
            repos_processed=repo_result.get('repositories_processed', 0),
            repos_inserted=repo_result.get('repositories_inserted', 0),
            repos_updated=repo_result.get('repositories_updated', 0),
            pr_extraction_completed=False
        )

        # Step 4: Extract second batch of Jira data
        jira_result_2 = self.extract_jira_data(
            'project = BEX and status CHANGED DURING ("-2d","-1d")',
            "Extracting second batch of Jira data (-2d to -1d)"
        )

        # Step 5: Test session-based GitHub processing
        print("\n🚀 Testing session-based GitHub processing...")
        from app.jobs.github.github_extractors import process_github_with_session_management

        result = process_github_with_session_management(
            self.session, self.github_integration, self.github_client,
            self.session_manager, extraction_session
        )

        print(f"\n✅ Scenario 2 Results:")
        print(f"   Status: {result.get('status')}")
        print(f"   Repos processed: {result.get('repos_processed', 0)}")
        print(f"   PRs processed: {result.get('pull_requests_processed', 0)}")
        print(f"   Combined PRs saved: {result.get('combined_pull_requests_saved', 0)}")

        return result

    def test_scenario_3(self):
        """Test Case 3: Jira complete, full repo extraction, partial PR extraction."""
        print("\n" + "="*80)
        print("🧪 TEST SCENARIO 3: Jira Complete, Full Repo + Partial PR Extraction")
        print("="*80)

        # Step 1: Extract first batch of Jira data
        jira_result_1 = self.extract_jira_data(
            'project = BEX and status CHANGED DURING ("-5d","-4d")',
            "Extracting first batch of Jira data (-5d to -4d)"
        )

        # Step 2: Process all repositories
        from app.jobs.github.github_extractors import extract_filtered_repositories
        repo_result = extract_filtered_repositories(
            self.session, self.github_integration, self.github_client
        )
        print(f"✅ Processed all {repo_result.get('repositories_processed', 0)} repositories")

        # Step 3: Process some pull requests
        pr_result = self.simulate_partial_pr_extraction(repos_to_process=5)

        # Step 4: Create forced session (full repo, partial PR extraction)
        extraction_session = self.create_forced_session(
            dev_status_data=jira_result_1['dev_status_data'],
            scenario_name="Full Repo + Partial PR Extraction",
            repo_extraction_completed=True,
            repos_processed=repo_result.get('repositories_processed', 0),
            repos_inserted=repo_result.get('repositories_inserted', 0),
            repos_updated=repo_result.get('repositories_updated', 0),
            pr_extraction_completed=False,
            pr_current_repo_index=5,  # Stopped at repo index 5
            prs_processed=pr_result.get('pull_requests_processed', 0),
            prs_inserted=pr_result.get('pull_requests_inserted', 0),
            prs_updated=pr_result.get('pull_requests_updated', 0)
        )

        # Step 5: Extract second batch of Jira data
        jira_result_2 = self.extract_jira_data(
            'project = BEX and status CHANGED DURING ("-2d","-1d")',
            "Extracting second batch of Jira data (-2d to -1d)"
        )

        # Step 6: Test session-based GitHub processing
        print("\n🚀 Testing session-based GitHub processing...")
        from app.jobs.github.github_extractors import process_github_with_session_management

        result = process_github_with_session_management(
            self.session, self.github_integration, self.github_client,
            self.session_manager, extraction_session
        )

        print(f"\n✅ Scenario 3 Results:")
        print(f"   Status: {result.get('status')}")
        print(f"   Repos processed: {result.get('repos_processed', 0)}")
        print(f"   PRs processed: {result.get('pull_requests_processed', 0)}")
        print(f"   Combined PRs saved: {result.get('combined_pull_requests_saved', 0)}")

        return result

    def run_test(self, scenario: int):
        """Run the selected test scenario."""
        try:
            self.setup()
            self.cleanup_existing_sessions()

            if scenario == 1:
                return self.test_scenario_1()
            elif scenario == 2:
                return self.test_scenario_2()
            elif scenario == 3:
                return self.test_scenario_3()
            else:
                raise ValueError(f"Invalid scenario: {scenario}")

        except Exception as e:
            logger.error(f"Test failed: {e}")
            raise
        finally:
            if self.session:
                self.session.close()


def main():
    """Main function to run the test script."""
    print("🧪 GitHub Session-Based Rate Limit Management Test Script")
    print("=" * 60)

    print("\nAvailable Test Scenarios:")
    print("1. Jira Complete, No GitHub Extraction")
    print("   - Processes Jira data from two time periods")
    print("   - Creates session with dev_status data")
    print("   - Tests full GitHub extraction with data combination")

    print("\n2. Jira Complete, Partial Repo Extraction (2 pages)")
    print("   - Processes Jira data and 2 pages of repositories")
    print("   - Creates session with partial repo state")
    print("   - Tests resuming with new repos + PR extraction")

    print("\n3. Jira Complete, Full Repo + Partial PR Extraction")
    print("   - Processes Jira data, all repos, and some PRs")
    print("   - Creates session with partial PR state")
    print("   - Tests resuming PR extraction from specific point")

    while True:
        try:
            choice = input("\nSelect scenario (1-3) or 'q' to quit: ").strip()

            if choice.lower() == 'q':
                print("👋 Goodbye!")
                return

            scenario = int(choice)
            if scenario not in [1, 2, 3]:
                print("❌ Please select 1, 2, or 3")
                continue

            print(f"\n🚀 Starting Test Scenario {scenario}...")

            tester = SessionManagementTester()
            result = tester.run_test(scenario)

            print(f"\n🎉 Test Scenario {scenario} completed!")
            print(f"Final Status: {result.get('status', 'unknown')}")

            if result.get('status') == 'completed':
                print("✅ Session management test PASSED")
            elif result.get('status') == 'rate_limit_reached':
                print("⚠️  Session management test PARTIAL (rate limit reached)")
                print(f"   Stopped at: {result.get('stopped_at')}")
            else:
                print("❌ Session management test FAILED")
                print(f"   Error: {result.get('error', 'Unknown error')}")

            # Ask if user wants to run another test
            another = input("\nRun another test? (y/n): ").strip().lower()
            if another != 'y':
                break

        except ValueError:
            print("❌ Please enter a valid number (1-3)")
        except KeyboardInterrupt:
            print("\n👋 Test interrupted by user")
            break
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            break


if __name__ == "__main__":
    print("⚠️  DEPRECATED: This test file is no longer functional after the GraphQL refactoring.")
    print("   The session management approach has been replaced with cursor-based checkpoints.")
    print("   Please use test_jobs.py for current testing capabilities.")
    print("   Exiting...")
    exit(1)
    # main()  # Commented out - no longer functional
