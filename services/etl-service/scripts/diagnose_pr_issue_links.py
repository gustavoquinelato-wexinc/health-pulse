#!/usr/bin/env python3
"""
PR-Issue Link Diagnostic Script

This script analyzes the staging table, pull requests, and repositories to diagnose
why PR-Issue links might not be created. It checks for:

1. Data in jira_dev_details_staging table
2. Pull requests in the database
3. Repository matches between staging and PRs
4. Issue key patterns in PR titles/bodies
5. Potential linking opportunities

Usage:
    python scripts/diagnose_pr_issue_links.py
"""

import sys
import os
import re
import warnings
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Suppress SQLAlchemy warnings for cleaner output
warnings.filterwarnings("ignore", message=".*relationship.*will copy column.*")
warnings.filterwarnings("ignore", category=UserWarning, module="sqlalchemy")

# Also suppress SQLAlchemy warnings at the logging level
import logging
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)

# Add the parent directory to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_database
from app.models.unified_models import (
    JiraDevDetailsStaging, PullRequest, Repository, Issue, Integration
)
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session


def analyze_staging_data(session: Session) -> Dict[str, Any]:
    """Analyze the jira_dev_details_staging table."""
    print("🔍 Analyzing Jira Dev Details Staging Table...")

    # Count total staging records
    total_staging = session.query(JiraDevDetailsStaging).count()
    print(f"   📊 Total staging records: {total_staging}")

    if total_staging == 0:
        print("   ⚠️  No staging data found!")
        return {"total": 0, "repositories": [], "sample_data": []}

    # Sample some staging data and parse JSON
    sample_staging = session.query(JiraDevDetailsStaging).join(Issue).limit(10).all()
    sample_data = []
    repo_urls = set()

    for record in sample_staging:
        try:
            # Parse the dev_status JSON payload
            dev_status_data = record.get_dev_status_data()

            # Debug: Show raw JSON structure for first few records (commented out for cleaner output)
            # if len(sample_data) < 3:
            #     print(f"   🔍 DEBUG - Raw dev_status_data keys for issue {record.issue.key if record.issue else 'Unknown'}: {list(dev_status_data.keys())}")
            #     if dev_status_data:
            #         print(f"      Sample content: {str(dev_status_data)[:200]}...")

            # Extract repository and PR information from dev_status
            repositories = []
            pull_requests = []

            # Try different possible structures
            if 'detail' in dev_status_data:
                for detail in dev_status_data['detail']:
                    if detail.get('_type') == 'repository':
                        repo_url = detail.get('url', '')
                        repositories.append(repo_url)
                        repo_urls.add(repo_url)
                    elif detail.get('_type') == 'pullrequest':
                        pr_url = detail.get('url', '')
                        pr_id = detail.get('id', '')
                        pr_status = detail.get('status', '')
                        pull_requests.append({
                            'url': pr_url,
                            'id': pr_id,
                            'status': pr_status
                        })

            # Also check for other possible structures
            elif 'repositories' in dev_status_data:
                repositories = dev_status_data.get('repositories', [])
                for repo in repositories:
                    if isinstance(repo, dict) and 'url' in repo:
                        repo_urls.add(repo['url'])
                    elif isinstance(repo, str):
                        repo_urls.add(repo)

            sample_data.append({
                "issue_key": record.issue.key if record.issue else "Unknown",
                "issue_id": record.issue_id,
                "repositories": repositories,
                "pull_requests": pull_requests,
                "processed": record.processed,
                "raw_data_keys": list(dev_status_data.keys()) if dev_status_data else []
            })

        except Exception as e:
            print(f"   ⚠️  Error parsing staging record {record.id}: {e}")
            import traceback
            traceback.print_exc()
            continue

    repo_urls = list(repo_urls)
    print(f"   📁 Unique repository URLs in staging: {len(repo_urls)}")

    print("   📋 Sample staging data:")
    for i, data in enumerate(sample_data[:5], 1):
        print(f"      {i}. Issue: {data['issue_key']} (ID: {data['issue_id']})")
        print(f"         Processed: {data['processed']}")
        print(f"         Repositories: {len(data['repositories'])}")
        for repo in data['repositories'][:2]:  # Show first 2 repos
            print(f"           - {repo}")
        print(f"         Pull Requests: {len(data['pull_requests'])}")
        for pr in data['pull_requests'][:2]:  # Show first 2 PRs
            print(f"           - {pr['url']} (Status: {pr['status']})")
        print()

    return {
        "total": total_staging,
        "repositories": repo_urls,
        "sample_data": sample_data
    }


def analyze_pull_requests(session: Session) -> Dict[str, Any]:
    """Analyze pull requests in the database."""
    print("🔍 Analyzing Pull Requests Table...")
    
    # Count total PRs
    total_prs = session.query(PullRequest).count()
    print(f"   📊 Total pull requests: {total_prs}")
    
    if total_prs == 0:
        print("   ⚠️  No pull requests found!")
        return {"total": 0, "repositories": [], "sample_data": []}
    
    # Get unique repositories from PRs
    pr_repos = session.query(
        distinct(Repository.full_name)
    ).join(
        PullRequest, Repository.id == PullRequest.repository_id
    ).all()
    
    repo_names = [repo[0] for repo in pr_repos if repo[0]]
    print(f"   📁 Unique repositories with PRs: {len(repo_names)}")
    
    # Sample some PR data
    sample_prs = session.query(PullRequest, Repository.full_name).join(
        Repository, Repository.id == PullRequest.repository_id
    ).limit(5).all()
    
    sample_data = []
    for pr, repo_name in sample_prs:
        sample_data.append({
            "number": pr.number,
            "title": pr.name,  # PullRequest model uses 'name' not 'title'
            "repository": repo_name,
            "state": pr.status,  # PullRequest model uses 'status' not 'state'
            "external_id": pr.external_id
        })
    
    print("   📋 Sample PR data:")
    for i, data in enumerate(sample_data, 1):
        print(f"      {i}. PR #{data['number']}: {data['title'][:60]}...")
        print(f"         Repo: {data['repository']}")
        print(f"         State: {data['state']}")
        print(f"         External ID: {data['external_id']}")
        print()
    
    return {
        "total": total_prs,
        "repositories": repo_names,
        "sample_data": sample_data
    }


def analyze_repositories(session: Session) -> Dict[str, Any]:
    """Analyze repositories in the database."""
    print("🔍 Analyzing Repositories Table...")
    
    # Count total repos
    total_repos = session.query(Repository).count()
    print(f"   📊 Total repositories: {total_repos}")
    
    if total_repos == 0:
        print("   ⚠️  No repositories found!")
        return {"total": 0, "sample_data": []}
    
    # Sample some repository data
    sample_repos = session.query(Repository).limit(10).all()
    sample_data = []
    
    for repo in sample_repos:
        sample_data.append({
            "id": repo.id,
            "full_name": repo.full_name,
            "external_id": repo.external_id,
            "url": repo.url,
            "name": repo.name
        })
    
    print("   📋 Sample repository data:")
    for i, data in enumerate(sample_data, 1):
        print(f"      {i}. {data['full_name']} (ID: {data['id']})")
        print(f"         External ID: {data['external_id']}")
        print(f"         URL: {data['url']}")
        print(f"         Name: {data['name']}")
        print()
    
    return {
        "total": total_repos,
        "sample_data": sample_data
    }


def find_repository_matches(staging_data: Dict, pr_data: Dict) -> Dict[str, Any]:
    """Find matches between staging repository URLs and PR repositories."""
    print("🔍 Analyzing Repository Matches...")
    
    staging_repos = set(staging_data["repositories"])
    pr_repos = set(pr_data["repositories"])
    
    print(f"   📊 Staging repos: {len(staging_repos)}")
    print(f"   📊 PR repos: {len(pr_repos)}")
    
    # Direct matches
    direct_matches = staging_repos.intersection(pr_repos)
    print(f"   ✅ Direct repository matches: {len(direct_matches)}")
    
    if direct_matches:
        print("   📋 Direct matches:")
        for match in list(direct_matches)[:5]:
            print(f"      - {match}")
    
    # Try to find partial matches (URL vs name)
    partial_matches = []
    for staging_url in staging_repos:
        if staging_url:
            # Extract repo name from URL (e.g., "wexinc/health-something" from URL)
            url_parts = staging_url.rstrip('/').split('/')
            if len(url_parts) >= 2:
                potential_name = f"{url_parts[-2]}/{url_parts[-1]}"
                if potential_name in pr_repos:
                    partial_matches.append((staging_url, potential_name))
    
    print(f"   🔗 Partial matches (URL → Name): {len(partial_matches)}")
    if partial_matches:
        print("   📋 Partial matches:")
        for staging_url, pr_name in partial_matches[:5]:
            print(f"      - {staging_url} → {pr_name}")
    
    return {
        "direct_matches": list(direct_matches),
        "partial_matches": partial_matches,
        "staging_only": list(staging_repos - pr_repos),
        "pr_only": list(pr_repos - staging_repos)
    }


def analyze_issue_key_patterns(session: Session) -> Dict[str, Any]:
    """Analyze issue key patterns in PR titles and bodies."""
    print("🔍 Analyzing Issue Key Patterns in PRs...")
    
    # Common Jira issue key patterns
    issue_key_patterns = [
        r'\b[A-Z]+-\d+\b',  # Standard Jira format: ABC-123
        r'\b[A-Z]{2,10}-\d+\b',  # Broader pattern
        r'#[A-Z]+-\d+',  # With hash prefix
        r'\([A-Z]+-\d+\)',  # In parentheses
    ]
    
    prs_with_keys = []
    total_checked = 0
    
    # Check recent PRs for issue keys
    recent_prs = session.query(PullRequest, Repository.full_name).join(
        Repository, Repository.id == PullRequest.repository_id
    ).limit(50).all()
    
    for pr, repo_name in recent_prs:
        total_checked += 1
        found_keys = []
        
        # Check name (title) and body
        text_to_check = f"{pr.name or ''} {pr.body or ''}"
        
        for pattern in issue_key_patterns:
            matches = re.findall(pattern, text_to_check, re.IGNORECASE)
            found_keys.extend(matches)
        
        if found_keys:
            prs_with_keys.append({
                "pr_number": pr.number,
                "repository": repo_name,
                "title": pr.name,  # Use 'name' field
                "found_keys": list(set(found_keys))  # Remove duplicates
            })
    
    print(f"   📊 PRs checked: {total_checked}")
    print(f"   🔑 PRs with potential issue keys: {len(prs_with_keys)}")
    
    if prs_with_keys:
        print("   📋 Sample PRs with issue keys:")
        for i, pr_data in enumerate(prs_with_keys[:5], 1):
            print(f"      {i}. PR #{pr_data['pr_number']}: {pr_data['title'][:50]}...")
            print(f"         Repo: {pr_data['repository']}")
            print(f"         Found keys: {pr_data['found_keys']}")
            print()
    
    return {
        "total_checked": total_checked,
        "prs_with_keys": len(prs_with_keys),
        "sample_prs": prs_with_keys[:10]
    }


def main():
    """Main diagnostic function."""
    print("🔍 PR-Issue Link Diagnostic Tool")
    print("=" * 50)
    
    try:
        database = get_database()
        with database.get_session() as session:
            # Analyze each component
            staging_analysis = analyze_staging_data(session)
            print()
            
            pr_analysis = analyze_pull_requests(session)
            print()
            
            repo_analysis = analyze_repositories(session)
            print()
            
            # Find matches
            if staging_analysis["total"] > 0 and pr_analysis["total"] > 0:
                match_analysis = find_repository_matches(staging_analysis, pr_analysis)
                print()
                
                issue_key_analysis = analyze_issue_key_patterns(session)
                print()
                
                # Summary and recommendations
                print("📋 DIAGNOSTIC SUMMARY")
                print("=" * 50)
                print(f"✅ Staging records: {staging_analysis['total']}")
                print(f"✅ Pull requests: {pr_analysis['total']}")
                print(f"✅ Repositories: {repo_analysis['total']}")
                print(f"🔗 Direct repo matches: {len(match_analysis['direct_matches'])}")
                print(f"🔗 Partial repo matches: {len(match_analysis['partial_matches'])}")
                print(f"🔑 PRs with issue keys: {issue_key_analysis['prs_with_keys']}")
                
                print("\n🎯 RECOMMENDATIONS")
                print("=" * 50)
                
                if len(match_analysis['direct_matches']) == 0 and len(match_analysis['partial_matches']) == 0:
                    print("❌ NO REPOSITORY MATCHES FOUND!")
                    print("   - Staging data and PRs are from different repositories")
                    print("   - Check if repository discovery is working correctly")
                    print("   - Verify staging data contains correct repository URLs")
                
                elif issue_key_analysis['prs_with_keys'] == 0:
                    print("❌ NO ISSUE KEYS FOUND IN PR TITLES/BODIES!")
                    print("   - PRs don't contain Jira issue keys")
                    print("   - Check if developers are following naming conventions")
                    print("   - Verify issue key pattern matching logic")
                
                else:
                    print("✅ Data looks good for linking!")
                    print("   - Check the PR-Issue linking logic in the code")
                    print("   - Verify the linking algorithm is running correctly")
            
            else:
                print("❌ MISSING BASIC DATA!")
                if staging_analysis["total"] == 0:
                    print("   - No staging data found - run Jira extraction first")
                if pr_analysis["total"] == 0:
                    print("   - No pull requests found - run GitHub extraction first")
    
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
