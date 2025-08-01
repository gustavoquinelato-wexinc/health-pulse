"""
Jira Data Extractors - Combined

Contains all extraction functions for Jira ETL operations.
Combines both basic and advanced extraction functions in a single module.
Each function handles a specific type of data extraction and processing.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.core.utils import DateTimeHelper
from app.models.unified_models import (
    Integration, Issuetype, Project, ProjectsIssuetypes, Status, ProjectsStatuses,
    Issue, IssueChangelog
)

from .jira_client import JiraAPIClient
from .jira_processor import JiraDataProcessor
from .jira_bulk_operations import perform_bulk_insert

logger = get_logger(__name__)


def has_useful_dev_status_data(dev_details: Dict) -> bool:
    """
    Check if dev_status response contains useful data (repositories, PRs, or branches).

    Args:
        dev_details: The dev_status response from Jira API

    Returns:
        True if the response contains repositories, pull requests, or branches
    """
    try:
        if not isinstance(dev_details, dict) or 'detail' not in dev_details:
            return False

        for detail in dev_details['detail']:
            if not isinstance(detail, dict):
                continue

            # Check for repositories
            repositories = detail.get('repositories', [])
            if repositories and len(repositories) > 0:
                return True

            # Check for pull requests
            pull_requests = detail.get('pullRequests', [])
            if pull_requests and len(pull_requests) > 0:
                return True

            # Check for branches (might indicate repository activity)
            branches = detail.get('branches', [])
            if branches and len(branches) > 0:
                return True

        return False

    except Exception:
        # If we can't parse it, assume it has useful data to avoid losing information
        return True


def extract_pr_links_from_dev_status(dev_details: Dict) -> List[Dict]:
    """
    Extract PR links from Jira dev_status API response.

    Args:
        dev_details: The dev_status response from Jira API

    Returns:
        List of dictionaries containing PR link information:
        [
            {
                'repo_id': str,
                'pr_number': int,
                'branch': str,
                'commit': str,
                'status': str
            },
            ...
        ]
    """
    pr_links = []

    try:
        if not isinstance(dev_details, dict) or 'detail' not in dev_details:
            return pr_links

        for detail in dev_details['detail']:
            if not isinstance(detail, dict):
                continue

            # Extract pull requests
            pull_requests = detail.get('pullRequests', [])
            for pr in pull_requests:
                if not isinstance(pr, dict):
                    continue

                # Extract repository information from Jira dev_status structure
                repo_id = pr.get('repositoryId')  # GitHub repository ID
                repo_full_name = pr.get('repositoryName')  # GitHub repository full name (e.g., "wexinc/health-api")

                # Both fields are required for the hybrid approach
                if not repo_id or not repo_full_name:
                    continue

                # Extract PR number - based on actual Jira dev_status structure
                pr_number = None

                # Try different possible fields for PR number
                if 'id' in pr:
                    pr_id = pr['id']
                    # Handle different ID formats
                    if isinstance(pr_id, int):
                        pr_number = pr_id
                    elif isinstance(pr_id, str):
                        if pr_id.isdigit():
                            pr_number = int(pr_id)
                        else:
                            # Try to extract number from string like "pull-request-123"
                            import re
                            match = re.search(r'(\d+)', pr_id)
                            if match:
                                pr_number = int(match.group(1))

                # Try pullRequestNumber field (from old staging logic)
                if not pr_number and 'pullRequestNumber' in pr:
                    try:
                        pr_number = int(pr['pullRequestNumber'])
                    except (ValueError, TypeError):
                        pass

                # Try extracting from URL if available
                if not pr_number and 'url' in pr:
                    import re
                    match = re.search(r'/pull/(\d+)', pr['url'])
                    if match:
                        pr_number = int(match.group(1))

                if repo_id and repo_full_name and pr_number:
                    # Extract branch name safely
                    branch_name = None
                    if 'branchName' in pr:
                        branch_name = pr['branchName']
                    elif 'source' in pr and isinstance(pr['source'], dict):
                        branch_name = pr['source'].get('branch')

                    # Extract commit ID safely
                    commit_id = None
                    if 'commitId' in pr:
                        commit_id = pr['commitId']
                    elif 'source' in pr and isinstance(pr['source'], dict):
                        commit_data = pr['source'].get('commit')
                        if isinstance(commit_data, dict):
                            commit_id = commit_data.get('id')
                        elif isinstance(commit_data, str):
                            commit_id = commit_data

                    pr_link = {
                        'repo_id': str(repo_id),
                        'repo_full_name': str(repo_full_name),
                        'pr_number': pr_number,
                        'branch': branch_name,
                        'commit': commit_id,
                        'status': pr.get('status', 'UNKNOWN').upper()
                    }
                    pr_links.append(pr_link)

            # Also check repositories for branch/commit information
            repositories = detail.get('repositories', [])
            for repo in repositories:
                if not isinstance(repo, dict):
                    continue

                repo_id = repo.get('id') or repo.get('name')
                if not repo_id:
                    continue

                # Check for commits that might be linked to PRs
                commits = repo.get('commits', [])
                for commit in commits:
                    if not isinstance(commit, dict):
                        continue

                    # Look for PR references in commit message or metadata
                    commit_message = commit.get('message', '')
                    if commit_message:
                        import re
                        # Look for PR references like "Merge pull request #123"
                        pr_match = re.search(r'#(\d+)', commit_message)
                        if pr_match:
                            pr_number = int(pr_match.group(1))
                            pr_link = {
                                'repo_id': str(repo_id),
                                'pr_number': pr_number,
                                'branch': None,
                                'commit': commit.get('id'),
                                'status': 'MERGED'  # Assume merged if found in commit
                            }
                            # Only add if not already present
                            if not any(link['repo_id'] == pr_link['repo_id'] and
                                     link['pr_number'] == pr_link['pr_number']
                                     for link in pr_links):
                                pr_links.append(pr_link)

    except Exception as e:
        logger.warning(f"Error extracting PR links from dev_status: {e}")

    return pr_links


def extract_projects_and_issuetypes(session: Session, jira_client: JiraAPIClient, integration: Integration, job_logger) -> Dict[str, Any]:
    """
    Extract projects and their associated issue types from Jira in a combined operation.
    This combines project extraction with project-issuetype relationship extraction.
    Projects are extracted first, then issue types from the same API response.

    Returns:
        Dict containing:
        - projects_processed: Number of projects processed
        - issuetypes_processed: Number of issue types processed
        - relationships_processed: Number of relationships processed
    """
    logger.info("Starting combined projects and issue types extraction")

    try:
        # Extract project keys from integration base_search
        project_keys = None
        if integration.base_search:
            # Parse project keys from base_search like "PROJECT IN (BDP,BEN,BEX,BST,CDB,CDH,EPE,FG,HBA,HDO,HDS)"
            import re
            match = re.search(r'PROJECT\s+IN\s*\(([^)]+)\)', integration.base_search, re.IGNORECASE)
            if match:
                project_keys = [key.strip().strip('"\'') for key in match.group(1).split(',')]

        # Get all projects from Jira
        jira_projects = jira_client.get_projects(expand="issueTypes", project_keys=project_keys)
        logger.info(f"Retrieved {len(jira_projects)} projects from Jira")

        if not jira_projects:
            job_logger.warning("No projects found in Jira")
            return {'projects_processed': 0, 'issuetypes_processed': 0, 'relationships_processed': 0}

        # Process projects data first
        projects_to_insert = []
        projects_to_update = []

        # Get existing projects for comparison
        existing_projects = {
            p.external_id: p for p in session.query(Project).filter(
                Project.integration_id == integration.id
            ).all()
        }

        processor = JiraDataProcessor(session, integration)
        current_time = datetime.now()
        projects_processed = 0

        for project_data in jira_projects:
            try:
                external_id = project_data.get('id')
                if not external_id:
                    continue

                processed_project = processor.process_project_data(project_data)
                if not processed_project:
                    continue

                if external_id in existing_projects:
                    # Check if update is needed
                    existing_project = existing_projects[external_id]
                    needs_update = False

                    # Check each field for changes (excluding external_id)
                    for field in ['key', 'name', 'project_type']:
                        new_value = processed_project.get(field)
                        current_value = getattr(existing_project, field, None)
                        if current_value != new_value:
                            needs_update = True
                            break

                    if needs_update:
                        # Update existing record
                        for key, value in processed_project.items():
                            if hasattr(existing_project, key.lower()):
                                setattr(existing_project, key.lower(), value)
                        existing_project.last_updated_at = current_time
                        projects_to_update.append(existing_project)
                else:
                    # Prepare for insert
                    project_data_dict = {
                        'integration_id': integration.id,
                        'external_id': external_id,
                        'key': processed_project.get('key', ''),
                        'name': processed_project.get('name', ''),
                        'project_type': processed_project.get('project_type'),
                        'client_id': integration.client_id,
                        'active': True,
                        'created_at': current_time,
                        'last_updated_at': current_time
                    }
                    projects_to_insert.append(project_data_dict)

                projects_processed += 1

            except Exception as e:
                job_logger.error(f"Error processing project {project_data.get('id', 'unknown')}: {e}")
                continue

        # Bulk operations for projects
        if projects_to_update:
            # Convert objects to dictionaries for bulk_update_mappings
            update_data = []
            for obj in projects_to_update:
                update_data.append({
                    'id': obj.id,
                    'integration_id': obj.integration_id,
                    'external_id': obj.external_id,
                    'key': obj.key,
                    'name': obj.name,
                    'project_type': getattr(obj, 'project_type', None),
                    'client_id': obj.client_id,
                    'active': obj.active,
                    'last_updated_at': obj.last_updated_at
                })
            session.bulk_update_mappings(Project, update_data)
            job_logger.progress(f"Updated {len(projects_to_update)} existing projects")

        if projects_to_insert:
            perform_bulk_insert(session, Project, projects_to_insert, "projects", job_logger)

        # Get all projects with their database IDs for issue type extraction
        all_projects = session.query(Project).filter(
            Project.integration_id == integration.id
        ).all()
        projects_dict = {p.external_id: p for p in all_projects}

        # Now extract issue types and project-issuetype relationships
        job_logger.progress("Starting issue types and project-issuetype relationships extraction")

        # Get existing issue types for comparison
        existing_issuetypes = {
            it.external_id: it for it in session.query(Issuetype).filter(
                Issuetype.integration_id == integration.id
            ).all()
        }

        issuetypes_to_insert = []
        issuetypes_to_update = []

        # Get existing project-issuetype relationships
        existing_relationships = session.query(ProjectsIssuetypes).filter(
            ProjectsIssuetypes.project_id.in_([p.id for p in all_projects])
        ).all()
        existing_relationships_set = {(rel.project_id, rel.issuetype_id) for rel in existing_relationships}

        relationships_to_insert = []
        all_issuetypes_from_projects = set()
        issuetypes_processed = 0

        # First pass: collect all unique issue types across all projects
        all_unique_issuetypes = {}  # {issuetype_external_id: issuetype_data}
        project_issuetype_relationships = []  # [(project_id, issuetype_external_id)]

        for project_data in jira_projects:
            project_external_id = project_data.get('id')
            project = projects_dict.get(project_external_id)

            if not project:
                job_logger.warning(f"Project with external_id {project_external_id} not found in database")
                continue

            # Collect unique issue types for this project
            project_issuetypes = project_data.get('issueTypes', [])
            job_logger.progress(f"Collecting issue types for project {project_data.get('key')}")

            project_issuetypes_set = set()

            for issuetype_data in project_issuetypes:
                issuetype_external_id = issuetype_data.get('id')
                if issuetype_external_id:
                    project_issuetypes_set.add(issuetype_external_id)
                    # Store the issue type data if we haven't seen it before
                    if issuetype_external_id not in all_unique_issuetypes:
                        all_unique_issuetypes[issuetype_external_id] = issuetype_data

            # Record project-issuetype relationships
            for issuetype_external_id in project_issuetypes_set:
                project_issuetype_relationships.append((project.id, issuetype_external_id))
                all_issuetypes_from_projects.add(issuetype_external_id)

        # Second pass: process each unique issue type only once
        for issuetype_external_id, issuetype_data in all_unique_issuetypes.items():
            try:
                # Process issue type data
                processed_issuetype = processor.process_issuetype_data(issuetype_data)
                if not processed_issuetype:
                    continue

                if issuetype_external_id in existing_issuetypes:
                    # Check if update is needed
                    existing_issuetype = existing_issuetypes[issuetype_external_id]
                    needs_update = False

                    # Check each field for changes (excluding external_id)
                    for field in ['original_name', 'issuetype_mapping_id', 'hierarchy_level', 'description']:
                        new_value = processed_issuetype.get(field)
                        current_value = getattr(existing_issuetype, field, None)
                        if current_value != new_value:
                            needs_update = True
                            break

                    if needs_update:
                        # Update existing record
                        for key, value in processed_issuetype.items():
                            if hasattr(existing_issuetype, key.lower()):
                                setattr(existing_issuetype, key.lower(), value)
                        existing_issuetype.last_updated_at = current_time
                        issuetypes_to_update.append(existing_issuetype)
                else:
                    # Prepare for insert
                    issuetype_data_dict = {
                        'integration_id': integration.id,
                        'external_id': issuetype_external_id,
                        'original_name': processed_issuetype.get('original_name', ''),
                        'issuetype_mapping_id': processed_issuetype.get('issuetype_mapping_id'),
                        'description': processed_issuetype.get('description'),
                        'hierarchy_level': processed_issuetype.get('hierarchy_level', 2),
                        'client_id': integration.client_id,
                        'active': processed_issuetype.get('active', True),
                        'created_at': current_time,
                        'last_updated_at': current_time
                    }
                    issuetypes_to_insert.append(issuetype_data_dict)

                issuetypes_processed += 1

            except Exception as e:
                job_logger.error(f"Error processing issue type {issuetype_data.get('id', 'unknown')}: {e}")
                continue

        # Bulk operations for issue types
        if issuetypes_to_update:
            # Convert objects to dictionaries for bulk_update_mappings
            update_data = []
            for obj in issuetypes_to_update:
                update_data.append({
                    'id': obj.id,
                    'integration_id': obj.integration_id,
                    'external_id': obj.external_id,
                    'original_name': obj.original_name,
                    'issuetype_mapping_id': getattr(obj, 'issuetype_mapping_id', None),
                    'description': getattr(obj, 'description', None),
                    'hierarchy_level': obj.hierarchy_level,
                    'client_id': obj.client_id,
                    'active': getattr(obj, 'active', True),
                    'last_updated_at': obj.last_updated_at
                })
            session.bulk_update_mappings(Issuetype, update_data)
            job_logger.progress(f"Updated {len(issuetypes_to_update)} existing issue types")

        if issuetypes_to_insert:
            perform_bulk_insert(session, Issuetype, issuetypes_to_insert, "issuetypes", job_logger)

        # Get updated issue types for relationship creation
        all_issuetypes = session.query(Issuetype).filter(
            Issuetype.integration_id == integration.id
        ).all()
        issuetypes_dict = {it.external_id: it for it in all_issuetypes}

        # Third pass: create relationships using the collected data
        current_relationships_jira = set()
        relationships_processed = 0

        for project_id, issuetype_external_id in project_issuetype_relationships:
            try:
                issuetype = issuetypes_dict.get(issuetype_external_id)

                if issuetype:
                    relationship_key = (project_id, issuetype.id)
                    current_relationships_jira.add(relationship_key)

                    if relationship_key not in existing_relationships_set:
                        relationships_to_insert.append({
                            'project_id': project_id,
                            'issuetype_id': issuetype.id
                        })
                        relationships_processed += 1

            except Exception as e:
                job_logger.error(f"Error creating relationship for project {project_id}, issuetype {issuetype_external_id}: {e}")
                continue

        # Bulk insert new relationships
        if relationships_to_insert:
            perform_bulk_insert(session, ProjectsIssuetypes, relationships_to_insert, "projects_issuetypes", job_logger)

        # Handle deletions - remove relationships that exist in DB but not in source
        relationships_to_delete = existing_relationships_set - current_relationships_jira

        if relationships_to_delete:
            job_logger.progress(f"Deleting {len(relationships_to_delete)} obsolete project-issuetype relationships")
            from app.jobs.jira.jira_bulk_operations import perform_bulk_delete_relationships
            perform_bulk_delete_relationships(session, "projects_issuetypes", relationships_to_delete, job_logger)

        # Mark issue types as inactive if they're no longer used in any project
        inactive_issuetypes = [
            it for it in existing_issuetypes.values()
            if it.external_id not in all_issuetypes_from_projects and getattr(it, 'active', True)
        ]

        if inactive_issuetypes:
            job_logger.progress(f"Marking {len(inactive_issuetypes)} issue types as inactive")
            for issuetype in inactive_issuetypes:
                issuetype.active = False
            session.commit()

        session.commit()
        job_logger.progress("Combined projects and issue types extraction completed successfully")

        return {
            'projects_processed': projects_processed,
            'issuetypes_processed': issuetypes_processed,
            'relationships_processed': relationships_processed
        }

    except Exception as e:
        session.rollback()
        job_logger.error(f"Error in combined projects and issue types extraction: {str(e)}")
        return {'projects_processed': 0, 'issuetypes_processed': 0, 'relationships_processed': 0}


def extract_projects_and_statuses(session: Session, jira_client: JiraAPIClient, integration: Integration, job_logger) -> Dict[str, Any]:
    """
    Extract projects and their associated statuses from Jira in a combined operation.
    This goes directly to get_project_statuses to extract both statuses and relationships efficiently.

    Returns:
        Dict containing:
        - statuses_processed: Number of statuses processed
        - relationships_processed: Number of relationships processed
    """
    logger.info("Starting combined projects and statuses extraction")

    try:
        # Get all projects from database (should already exist from step 1)
        all_projects = session.query(Project).filter(
            Project.integration_id == integration.id
        ).all()

        if not all_projects:
            job_logger.warning("No projects found in database. Please run projects extraction first.")
            return {'statuses_processed': 0, 'relationships_processed': 0}

        # Get existing statuses for comparison
        existing_statuses = {
            s.external_id: s for s in session.query(Status).filter(
                Status.integration_id == integration.id
            ).all()
        }

        processor = JiraDataProcessor(session, integration)
        statuses_to_insert = []
        statuses_to_update = []
        current_time = datetime.now()
        statuses_processed = 0

        # Get existing project-status relationships
        existing_relationships = session.query(ProjectsStatuses).filter(
            ProjectsStatuses.project_id.in_([p.id for p in all_projects])
        ).all()
        existing_relationships_set = {(rel.project_id, rel.status_id) for rel in existing_relationships}

        relationships_to_insert = []
        all_statuses_from_projects = set()
        relationships_processed = 0

        # First pass: collect all unique statuses across all projects
        all_unique_statuses = {}  # {status_external_id: status_data}
        project_status_relationships = []  # [(project_id, status_external_id)]

        for project in all_projects:
            try:
                project_key = project.key
                project_statuses_data = jira_client.get_project_statuses(project_key)
                job_logger.progress(f"Collecting statuses for project {project_key}")

                # Collect unique statuses for this project
                project_statuses_set = set()

                for issuetype_data in project_statuses_data:
                    statuses_list = issuetype_data.get('statuses', [])

                    for status_data in statuses_list:
                        status_external_id = status_data.get('id')
                        if status_external_id:
                            project_statuses_set.add(status_external_id)
                            # Store the status data if we haven't seen it before
                            if status_external_id not in all_unique_statuses:
                                all_unique_statuses[status_external_id] = status_data

                # Record project-status relationships
                for status_external_id in project_statuses_set:
                    project_status_relationships.append((project.id, status_external_id))
                    all_statuses_from_projects.add(status_external_id)

            except Exception as e:
                job_logger.error(f"Error collecting statuses for project {project.external_id}: {e}")
                continue

        # Second pass: process each unique status only once
        for status_external_id, status_data in all_unique_statuses.items():
            try:
                # Process status data
                processed_status = processor.process_status_data(status_data)
                if not processed_status:
                    continue

                if status_external_id in existing_statuses:
                    # Check if update is needed
                    existing_status = existing_statuses[status_external_id]
                    needs_update = False

                    # Check each field for changes (excluding external_id)
                    for field in ['original_name', 'status_mapping_id', 'category', 'description']:
                        new_value = processed_status.get(field)
                        current_value = getattr(existing_status, field, None)
                        if current_value != new_value:
                            needs_update = True
                            break

                    if needs_update:
                        # Update existing record
                        for key, value in processed_status.items():
                            if hasattr(existing_status, key.lower()):
                                setattr(existing_status, key.lower(), value)
                        existing_status.last_updated_at = current_time
                        statuses_to_update.append(existing_status)
                else:
                    # Prepare for insert
                    status_data_dict = {
                        'integration_id': integration.id,
                        'external_id': status_external_id,
                        'original_name': processed_status.get('original_name', ''),
                        'status_mapping_id': processed_status.get('status_mapping_id'),
                        'category': processed_status.get('category', ''),
                        'description': processed_status.get('description'),
                        'client_id': integration.client_id,
                        'active': processed_status.get('active', True),
                        'created_at': current_time,
                        'last_updated_at': current_time
                    }
                    statuses_to_insert.append(status_data_dict)

                statuses_processed += 1

            except Exception as e:
                job_logger.error(f"Error processing status {status_data.get('id', 'unknown')}: {e}")
                continue

        # Bulk operations for statuses
        if statuses_to_update:
            # Convert objects to dictionaries for bulk_update_mappings
            update_data = []
            for obj in statuses_to_update:
                update_data.append({
                    'id': obj.id,
                    'integration_id': obj.integration_id,
                    'external_id': obj.external_id,
                    'original_name': obj.original_name,
                    'status_mapping_id': getattr(obj, 'status_mapping_id', None),
                    'category': obj.category,
                    'description': getattr(obj, 'description', None),
                    'client_id': obj.client_id,
                    'active': getattr(obj, 'active', True),
                    'last_updated_at': obj.last_updated_at
                })
            session.bulk_update_mappings(Status, update_data)
            job_logger.progress(f"Updated {len(statuses_to_update)} existing statuses")

        if statuses_to_insert:
            perform_bulk_insert(session, Status, statuses_to_insert, "statuses", job_logger)

        # Get updated statuses for relationship creation
        all_statuses = session.query(Status).filter(
            Status.integration_id == integration.id
        ).all()
        statuses_dict = {s.external_id: s for s in all_statuses}

        # Third pass: create relationships using the collected data
        current_relationships_jira = set()

        for project_id, status_external_id in project_status_relationships:
            try:
                status = statuses_dict.get(status_external_id)

                if status:
                    relationship_key = (project_id, status.id)
                    current_relationships_jira.add(relationship_key)

                    if relationship_key not in existing_relationships_set:
                        relationships_to_insert.append({
                            'project_id': project_id,
                            'status_id': status.id
                        })
                        relationships_processed += 1

            except Exception as e:
                job_logger.error(f"Error creating relationship for project {project_id}, status {status_external_id}: {e}")
                continue

        # Bulk insert new relationships
        if relationships_to_insert:
            perform_bulk_insert(session, ProjectsStatuses, relationships_to_insert, "projects_statuses", job_logger)

        # Handle deletions - remove relationships that exist in DB but not in source
        relationships_to_delete = existing_relationships_set - current_relationships_jira

        if relationships_to_delete:
            job_logger.progress(f"Deleting {len(relationships_to_delete)} obsolete project-status relationships")
            from app.jobs.jira.jira_bulk_operations import perform_bulk_delete_relationships
            perform_bulk_delete_relationships(session, "projects_statuses", relationships_to_delete, job_logger)

        # Mark statuses as inactive if they're no longer used in any project
        inactive_statuses = [
            s for s in existing_statuses.values()
            if s.external_id not in all_statuses_from_projects and getattr(s, 'active', True)
        ]

        if inactive_statuses:
            job_logger.progress(f"Marking {len(inactive_statuses)} statuses as inactive")
            for status in inactive_statuses:
                status.active = False
            session.commit()

        session.commit()
        job_logger.progress("Combined projects and statuses extraction completed successfully")

        return {
            'statuses_processed': statuses_processed,
            'relationships_processed': relationships_processed
        }

    except Exception as e:
        session.rollback()
        job_logger.error(f"Error in combined projects and statuses extraction: {str(e)}")
        return {'statuses_processed': 0, 'relationships_processed': 0}


async def extract_work_items_and_changelogs(session: Session, jira_client: JiraAPIClient, integration: Integration, job_logger, start_date=None, websocket_manager=None, update_sync_timestamp: bool = True) -> Dict[str, Any]:
    """Extract and process Jira work items and their changelogs together using bulk operations with batching for performance.

    Returns:
        Dict containing:
        - issues_processed: Number of issues processed
        - changelogs_processed: Number of changelogs processed
        - issue_keys: List of issue keys processed
    """
    try:
        processor = JiraDataProcessor(session, integration)

        # Capture extraction start time (to be saved at the end) - using server local time
        from datetime import datetime
        extraction_start_time = datetime.now()
        job_logger.progress(f"[STARTING] Extraction started at: {extraction_start_time.strftime('%Y-%m-%d %H:%M')}")

        # Load all reference data in single queries
        statuses_list = session.query(Status).filter(Status.integration_id == integration.id).all()
        issuetypes_list = session.query(Issuetype).filter(Issuetype.integration_id == integration.id).all()
        projects_list = session.query(Project).filter(Project.integration_id == integration.id).all()

        # Create comprehensive mappings
        statuses_dict = {s.external_id: s for s in statuses_list}
        issuetypes_dict = {i.external_id: i for i in issuetypes_list}
        projects_dict = {p.external_id: p for p in projects_list}

        # Create ID-only mappings for bulk operations
        statuses_id_dict = {s.external_id: s.id for s in statuses_list}
        issuetypes_id_dict = {i.external_id: i.id for i in issuetypes_list}
        projects_id_dict = {p.external_id: p.id for p in projects_list}

        job_logger.progress(f"[LOADED] Reference data: {len(statuses_dict)} statuses, {len(issuetypes_dict)} issuetypes, {len(projects_dict)} projects")

        # Fetch recently updated issues
        # Use start_date parameter if provided, otherwise fall back to integration.last_sync_at
        if start_date:
            last_sync = start_date
        else:
            last_sync = integration.last_sync_at or datetime.now() - timedelta(days=30)

        # Format datetime for Jira JQL (YYYY-MM-DD HH:mm format)
        jira_datetime = last_sync.strftime('%Y-%m-%d %H:%M')

        # Use base_search from integration instead of environment variable
        base_search = integration.base_search

        jql = f"""
                {base_search}
                AND updated >= '{jira_datetime}'
                ORDER BY updated DESC
        """
        #AND key = BEN-7914

        job_logger.progress(f"[FETCHING] Fetching issues with JQL: {jql}")



        def progress_callback(message):
            job_logger.progress(f"[FETCHED] {message}")

        # Run the blocking API call in a thread pool to avoid blocking the event loop
        import asyncio
        import concurrent.futures

        def get_issues_sync():
            return jira_client.get_issues(jql=jql, max_results=100, progress_callback=progress_callback)

        # Run in thread pool with timeout
        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = loop.run_in_executor(executor, get_issues_sync)
                all_issues = await asyncio.wait_for(future, timeout=300)  # 5 minute timeout
        except asyncio.TimeoutError:
            job_logger.error("Issue fetching timed out after 5 minutes")
            return {
                'success': False,
                'error': 'Issue fetching timed out after 5 minutes',
                'issues_processed': 0,
                'changelogs_processed': 0,
                'issue_keys': []
            }
        except Exception as e:
            job_logger.error(f"Error during async issue fetching: {e}")
            return {
                'success': False,
                'error': f'Error during issue fetching: {str(e)}',
                'issues_processed': 0,
                'changelogs_processed': 0,
                'issue_keys': []
            }
        job_logger.progress(f"[TOTAL] Total issues fetched: {len(all_issues)}")

        if not all_issues:
            job_logger.warning("No issues found for the given criteria")

            # Update integration.last_sync_at even when no issues found (to prevent re-processing same time range)
            if update_sync_timestamp:
                truncated_start_time = extraction_start_time.replace(second=0, microsecond=0)
                integration.last_sync_at = truncated_start_time
                session.commit()
                job_logger.progress(f"[SYNC_TIME] Updated integration last_sync_at to: {truncated_start_time.strftime('%Y-%m-%d %H:%M')}")
            else:
                job_logger.progress("[SYNC_TIME] Skipped updating integration last_sync_at (test mode)")

            return {'success': True, 'issues_processed': 0, 'changelogs_processed': 0, 'issue_keys': []}

        # Get existing issues to determine updates vs inserts
        external_ids = [issue.get('id') for issue in all_issues if issue.get('id')]

        # Process in batches to avoid large IN clauses
        existing_issues = {}
        batch_size = 1000
        for i in range(0, len(external_ids), batch_size):
            batch_ids = external_ids[i:i + batch_size]
            batch_existing = session.query(Issue).filter(
                Issue.integration_id == integration.id,
                Issue.external_id.in_(batch_ids)
            ).all()

            for issue in batch_existing:
                existing_issues[issue.external_id] = issue

        # Process issues
        issues_to_insert = []
        issues_to_update = []
        processed_count = 0
        processed_issue_keys = []
        issue_changelogs = {}  # Store changelog data by issue key
        current_time = datetime.now()

        job_logger.progress(f"[PROCESSING] Starting to process {len(all_issues)} issues...")

        for issue_data in all_issues:
            try:
                # Add small delay every 10 issues to prevent blocking
                if len(processed_issue_keys) % 10 == 0:
                    import time
                    time.sleep(0.001)  # 1ms delay

                external_id = issue_data.get('id')
                if not external_id:
                    continue

                processed_issue = processor.process_issue_data(issue_data)
                if not processed_issue:
                    continue

                if external_id in existing_issues:
                    # Update existing issue - check for actual field changes
                    existing_issue = existing_issues[external_id]
                    has_changes = False

                    # Map external IDs to database IDs and check for changes
                    project_external_id = processed_issue.get('project_id')
                    new_project_id = projects_dict[project_external_id].id if project_external_id and project_external_id in projects_dict else None
                    if existing_issue.project_id != new_project_id:
                        existing_issue.project_id = new_project_id
                        has_changes = True

                    issuetype_external_id = processed_issue.get('issuetype_id')
                    new_issuetype_id = issuetypes_dict[issuetype_external_id].id if issuetype_external_id and issuetype_external_id in issuetypes_dict else None
                    if existing_issue.issuetype_id != new_issuetype_id:
                        existing_issue.issuetype_id = new_issuetype_id
                        has_changes = True

                    status_external_id = processed_issue.get('status_id')
                    new_status_id = statuses_id_dict.get(status_external_id) if status_external_id else None
                    if existing_issue.status_id != new_status_id:
                        existing_issue.status_id = new_status_id
                        has_changes = True

                    # Check other fields for changes
                    for key, value in processed_issue.items():
                        if key in ['project_id', 'issuetype_id', 'status_id']:
                            continue

                        if hasattr(existing_issue, key):
                            if key == 'labels':
                                if isinstance(value, list):
                                    value = ','.join(value)
                                else:
                                    value = str(value) if value else None

                            current_value = getattr(existing_issue, key)
                            if current_value != value:
                                setattr(existing_issue, key, value)
                                has_changes = True

                    # Only add to update list if there were actual changes
                    if has_changes:
                        existing_issue.last_updated_at = current_time
                        issues_to_update.append(existing_issue)
                        processed_issue_keys.append(existing_issue.key)
                else:
                    # Prepare for insert
                    project_external_id = processed_issue.get('project_id')
                    project_id = projects_id_dict.get(project_external_id) if project_external_id else None

                    issuetype_external_id = processed_issue.get('issuetype_id')
                    issuetype_id = issuetypes_id_dict.get(issuetype_external_id) if issuetype_external_id else None

                    status_external_id = processed_issue.get('status_id')
                    status_id = statuses_id_dict.get(status_external_id) if status_external_id else None

                    issue_data_for_insert = {
                        'integration_id': integration.id,
                        'external_id': external_id,
                        'key': processed_issue.get('key'),
                        'summary': processed_issue.get('summary'),
                        'team': processed_issue.get('team'),
                        'created': processed_issue.get('created'),
                        'updated': processed_issue.get('updated'),
                        'work_first_started_at': processed_issue.get('work_first_started_at'),
                        'work_first_completed_at': processed_issue.get('work_first_completed_at'),
                        'priority': processed_issue.get('priority'),
                        'resolution': processed_issue.get('resolution'),
                        'labels': ','.join(processed_issue.get('labels', [])) if isinstance(processed_issue.get('labels'), list) else str(processed_issue.get('labels', '')) if processed_issue.get('labels') is not None else None,
                        'story_points': processed_issue.get('story_points'),
                        'assignee': processed_issue.get('assignee'),
                        'project_id': project_id,
                        'issuetype_id': issuetype_id,
                        'status_id': status_id,
                        'parent_external_id': processed_issue.get('parent_id'),
                        'code_changed': processed_issue.get('code_changed', False),
                        'client_id': integration.client_id,
                        'active': True,
                        'created_at': current_time,
                        'last_updated_at': current_time
                    }
                    issues_to_insert.append(issue_data_for_insert)

                processed_count += 1

                # Send progress update every 50 issues
                if websocket_manager and processed_count % 50 == 0:
                    # Calculate progress within the 35-45% range for issue processing
                    process_progress = 35.0 + (processed_count / len(all_issues)) * 10.0
                    progress_message = f"Processing issues: {processed_count:,} of {len(all_issues):,} ({processed_count/len(all_issues)*100:.1f}%)"

                    try:
                        import asyncio
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(websocket_manager.send_progress_update(
                                "jira_sync",
                                process_progress,
                                progress_message
                            ))
                    except Exception:
                        pass

                # Track issue key and changelog data for processing
                issue_key = processed_issue.get('key', '') or issue_data.get('key', '')
                if issue_key:
                    processed_issue_keys.append(issue_key)

                    # Process changelogs from the issue data (already included via expand=changelog)
                    changelog_data = issue_data.get('changelog', {})
                    if changelog_data and changelog_data.get('histories'):
                        # Store changelog data with issue key for later processing
                        issue_changelogs[issue_key] = changelog_data.get('histories', [])

            except Exception as e:
                logger.error(f"Error processing issue {issue_data.get('key', 'unknown')}: {e}")
                continue

        # Perform bulk operations
        if issues_to_update:
            job_logger.progress(f"Starting batch updates for {len(issues_to_update)} issues...")
            update_data = []
            for obj in issues_to_update:
                update_data.append({
                    'id': obj.id,
                    'integration_id': obj.integration_id,
                    'external_id': obj.external_id,
                    'key': obj.key,
                    'summary': obj.summary,
                    'team': obj.team,
                    'created': obj.created,
                    'updated': obj.updated,
                    'work_first_started_at': obj.work_first_started_at,
                    'work_first_completed_at': obj.work_first_completed_at,
                    'priority': obj.priority,
                    'resolution': obj.resolution,
                    'labels': str(obj.labels) if obj.labels is not None else None,
                    'story_points': obj.story_points,
                    'assignee': obj.assignee,
                    'project_id': obj.project_id,
                    'issuetype_id': obj.issuetype_id,
                    'status_id': obj.status_id,
                    'parent_external_id': obj.parent_external_id,
                    'code_changed': obj.code_changed,
                    'client_id': obj.client_id,
                    'active': obj.active,
                    'last_updated_at': obj.last_updated_at
                })

            session.bulk_update_mappings(Issue, update_data)
            job_logger.progress(f"[COMPLETED] Completed updating {len(issues_to_update)} existing issues")

        if issues_to_insert:
            job_logger.progress(f"Starting bulk inserts for {len(issues_to_insert)} issues...")
            perform_bulk_insert(session, Issue, issues_to_insert, "issues", job_logger)
            job_logger.progress(f"[COMPLETED] Completed bulk inserting {len(issues_to_insert)} new issues")

        session.commit()
        job_logger.progress(f"[SUCCESS] Successfully processed {processed_count} issues total")

        # Now process changelogs for all processed issues
        job_logger.progress(f"[STARTING] Starting changelog processing for {len(processed_issue_keys)} issues...")

        changelogs_processed = 0
        if processed_issue_keys:
            changelogs_processed = process_changelogs_for_issues(
                session, jira_client, integration, processed_issue_keys,
                statuses_dict, job_logger, issue_changelogs, websocket_manager
            )



        # Update integration.last_sync_at to extraction start time (truncated to %Y-%m-%d %H:%M format)
        # This ensures we capture the start time to prevent losing changes made during extraction
        if update_sync_timestamp:
            truncated_start_time = extraction_start_time.replace(second=0, microsecond=0)
            integration.last_sync_at = truncated_start_time
            session.commit()
            job_logger.progress(f"[SYNC_TIME] Updated integration last_sync_at to: {truncated_start_time.strftime('%Y-%m-%d %H:%M')}")
        else:
            job_logger.progress("[SYNC_TIME] Skipped updating integration last_sync_at (test mode)")

        return {
            'success': True,
            'issues_processed': processed_count,
            'changelogs_processed': changelogs_processed,
            'issue_keys': processed_issue_keys,
            'issue_changelogs': issue_changelogs  # Include extracted changelog data
        }

    except Exception as e:
        session.rollback()
        job_logger.error(f"Error in work items and changelogs extraction: {str(e)}")
        return {'success': False, 'error': str(e), 'issues_processed': 0, 'changelogs_processed': 0, 'issue_keys': [], 'issue_changelogs': {}}




def process_changelogs_for_issues(session: Session, jira_client: JiraAPIClient, integration: Integration,
                                 issue_keys: List[str], statuses_dict: Dict[str, Any], job_logger,
                                 issue_changelogs: Dict[str, List[Dict]] = None, websocket_manager=None) -> int:
    """Process changelogs for a list of issues and calculate enhanced workflow metrics.

    Args:
        session: Database session
        jira_client: Jira API client (kept for compatibility, not used when issue_changelogs provided)
        integration: Integration object
        issue_keys: List of issue keys to process changelogs for
        statuses_dict: Dictionary mapping status external_ids to status objects
        job_logger: Logger for progress tracking
        issue_changelogs: Optional dict of changelog data by issue key (from expand=changelog)

    Returns:
        Number of changelogs processed
    """
    try:
        processor = JiraDataProcessor(session, integration)

        # Get all issues from database that we need to process
        issues_in_db = session.query(Issue).filter(
            Issue.integration_id == integration.id,
            Issue.key.in_(issue_keys)
        ).all()

        if not issues_in_db:
            job_logger.warning("No issues found in database for changelog processing")
            return 0



        # Get existing changelogs to avoid duplicates
        existing_changelogs = session.query(IssueChangelog).filter(
            IssueChangelog.issue_id.in_([issue.id for issue in issues_in_db])
        ).all()

        existing_changelog_keys = {
            (cl.issue_id, cl.external_id) for cl in existing_changelogs
        }

        changelogs_to_insert = []
        current_time = datetime.now()
        total_changelogs_processed = 0

        job_logger.progress(f"[PROCESSING] Processing changelogs for {len(issues_in_db)} issues...")

        # Process each issue's changelogs
        issues_processed = 0
        for issue in issues_in_db:
            try:

                issue_key = issue.key

                # Use embedded changelog data if available, otherwise fall back to API call
                if issue_changelogs and issue_key in issue_changelogs:
                    changelogs_data = issue_changelogs[issue_key]
                else:
                    # Only log fallback API calls since they're less common and more important
                    job_logger.progress(f"[FETCHING] Fetching changelogs for issue {issue_key} (fallback)")
                    changelogs_data = jira_client.get_issue_changelogs(issue_key)

                if not changelogs_data:
                    continue

                # Process and sort changelog entries by date for this issue
                changelog_entries_for_processing = []

                # Process each changelog entry
                for changelog_data in changelogs_data:
                    try:
                        changelog_external_id = changelog_data.get('id')
                        if not changelog_external_id:
                            continue

                        # Skip if changelog already exists
                        if (issue.id, changelog_external_id) in existing_changelog_keys:
                            continue

                        processed_changelog = processor.process_changelog_data(changelog_data)
                        if not processed_changelog:
                            continue

                        # Map status external IDs to database IDs
                        from_status_external_id = processed_changelog.get('from_status_id')
                        to_status_external_id = processed_changelog.get('to_status_id')

                        from_status_id = None
                        to_status_id = None

                        if from_status_external_id and from_status_external_id in statuses_dict:
                            from_status_id = statuses_dict[from_status_external_id].id

                        if to_status_external_id and to_status_external_id in statuses_dict:
                            to_status_id = statuses_dict[to_status_external_id].id

                        changelog_entry = {
                            'integration_id': integration.id,
                            'issue_id': issue.id,
                            'external_id': changelog_external_id,
                            'from_status_id': from_status_id,
                            'to_status_id': to_status_id,
                            'transition_change_date': processed_changelog.get('changed_at'),
                            'changed_by': processed_changelog.get('author'),
                            'client_id': integration.client_id,
                            'active': True,
                            'created_at': current_time,
                            'last_updated_at': current_time
                        }

                        changelog_entries_for_processing.append(changelog_entry)
                        total_changelogs_processed += 1

                    except Exception as e:
                        job_logger.error(f"Error processing changelog {changelog_data.get('id', 'unknown')} for issue {issue_key}: {e}")
                        continue

                # Sort changelog entries by transition_change_date and calculate timing fields
                if changelog_entries_for_processing:
                    changelog_entries_for_processing.sort(key=lambda x: x['transition_change_date'] or datetime.min)

                    # Calculate transition_start_date and time_in_status_seconds for each entry
                    for i, changelog_entry in enumerate(changelog_entries_for_processing):
                        if i == 0:
                            # First transition starts from issue creation - preserve local time
                            changelog_entry['transition_start_date'] = DateTimeHelper.normalize_to_naive_local(issue.created)
                        else:
                            # Subsequent transitions start from previous transition date
                            changelog_entry['transition_start_date'] = DateTimeHelper.normalize_to_naive_local(
                                changelog_entries_for_processing[i-1]['transition_change_date']
                            )

                        # Calculate time in status (seconds with millisecond precision) using centralized utility
                        changelog_entry['time_in_status_seconds'] = DateTimeHelper.calculate_time_difference_seconds_float(
                            changelog_entry['transition_start_date'],
                            changelog_entry['transition_change_date']
                        )

                    # Add processed entries to bulk insert list
                    changelogs_to_insert.extend(changelog_entries_for_processing)

                # Track progress
                issues_processed += 1

                # Log progress every 50 issues and send websocket updates every 25 issues
                if issues_processed % 50 == 0:
                    job_logger.progress(f"[PROGRESS] Processed changelogs for {issues_processed:,} of {len(issues_in_db):,} issues ({issues_processed/len(issues_in_db)*100:.1f}%)")

                # Send progress update every 25 issues
                if websocket_manager and issues_processed % 25 == 0:
                    # Calculate progress within the 45-50% range for changelog processing
                    changelog_progress = 45.0 + (issues_processed / len(issues_in_db)) * 5.0
                    progress_message = f"Processing changelogs: {issues_processed:,} of {len(issues_in_db):,} issues ({issues_processed/len(issues_in_db)*100:.1f}%)"

                    try:
                        import asyncio
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(websocket_manager.send_progress_update(
                                "jira_sync",
                                changelog_progress,
                                progress_message
                            ))
                    except Exception:
                        pass

            except Exception as e:
                job_logger.error(f"Error processing changelogs for issue {issue.key}: {e}")
                issues_processed += 1  # Still count it as processed for progress tracking
                continue

        # Bulk insert changelogs
        if changelogs_to_insert:
            job_logger.progress(f"[INSERTING] Bulk inserting {len(changelogs_to_insert)} changelogs...")
            # Debug: Print first changelog to see the data structure
            if changelogs_to_insert:
                job_logger.progress(f"[DEBUG] First changelog data: {changelogs_to_insert[0]}")
            perform_bulk_insert(session, IssueChangelog, changelogs_to_insert, "issue_changelogs", job_logger)

        # Calculate and update enhanced workflow metrics from database changelogs
        if issues_in_db:
            job_logger.progress(f"[CALCULATING] Calculating enhanced workflow metrics for {len(issues_in_db)} issues from database changelogs...")

            # Get all changelogs for the processed issues from database
            issue_ids = [issue.id for issue in issues_in_db]
            all_changelogs = session.query(IssueChangelog).filter(
                IssueChangelog.issue_id.in_(issue_ids)
            ).order_by(IssueChangelog.issue_id, IssueChangelog.transition_change_date).all()

            # Group changelogs by issue_id
            changelogs_by_issue = {}
            for changelog in all_changelogs:
                if changelog.issue_id not in changelogs_by_issue:
                    changelogs_by_issue[changelog.issue_id] = []
                changelogs_by_issue[changelog.issue_id].append(changelog)

            # Calculate enhanced workflow metrics for each issue
            issues_to_update_metrics = []
            for issue in issues_in_db:
                issue_changelogs = changelogs_by_issue.get(issue.id, [])

                # Get current status category
                current_status_category = None
                if issue.status_id:
                    for status_external_id, status_obj in statuses_dict.items():
                        if status_obj.id == issue.status_id:
                            current_status_category = getattr(status_obj, 'category', '').lower()
                            break

                # Legacy date calculation removed - now using enhanced workflow metrics only

                # Calculate enhanced workflow metrics
                enhanced_metrics = calculate_enhanced_workflow_metrics(
                    issue_changelogs, statuses_dict
                )

                # Check if any enhanced workflow values have changed
                needs_update = (
                    issue.work_first_committed_at != enhanced_metrics['work_first_committed_at'] or
                    issue.work_first_started_at != enhanced_metrics['work_first_started_at'] or
                    issue.work_last_started_at != enhanced_metrics['work_last_started_at'] or
                    issue.work_first_completed_at != enhanced_metrics['work_first_completed_at'] or
                    issue.work_last_completed_at != enhanced_metrics['work_last_completed_at'] or
                    issue.total_work_starts != enhanced_metrics['total_work_starts'] or
                    issue.total_completions != enhanced_metrics['total_completions'] or
                    issue.total_backlog_returns != enhanced_metrics['total_backlog_returns'] or
                    abs((issue.total_work_time_seconds or 0) - enhanced_metrics['total_work_time_seconds']) > 0.1 or
                    abs((issue.total_review_time_seconds or 0) - enhanced_metrics['total_review_time_seconds']) > 0.1 or
                    abs((issue.total_cycle_time_seconds or 0) - enhanced_metrics['total_cycle_time_seconds']) > 0.1 or
                    abs((issue.total_lead_time_seconds or 0) - enhanced_metrics['total_lead_time_seconds']) > 0.1 or
                    issue.workflow_complexity_score != enhanced_metrics['workflow_complexity_score'] or
                    issue.rework_indicator != enhanced_metrics['rework_indicator'] or
                    issue.direct_completion != enhanced_metrics['direct_completion']
                )

                if needs_update:
                    # Update enhanced workflow fields
                    issue.work_first_committed_at = enhanced_metrics['work_first_committed_at']
                    issue.work_first_started_at = enhanced_metrics['work_first_started_at']
                    issue.work_last_started_at = enhanced_metrics['work_last_started_at']
                    issue.work_first_completed_at = enhanced_metrics['work_first_completed_at']
                    issue.work_last_completed_at = enhanced_metrics['work_last_completed_at']
                    issue.total_work_starts = enhanced_metrics['total_work_starts']
                    issue.total_completions = enhanced_metrics['total_completions']
                    issue.total_backlog_returns = enhanced_metrics['total_backlog_returns']
                    issue.total_work_time_seconds = enhanced_metrics['total_work_time_seconds']
                    issue.total_review_time_seconds = enhanced_metrics['total_review_time_seconds']
                    issue.total_cycle_time_seconds = enhanced_metrics['total_cycle_time_seconds']
                    issue.total_lead_time_seconds = enhanced_metrics['total_lead_time_seconds']
                    issue.workflow_complexity_score = enhanced_metrics['workflow_complexity_score']
                    issue.rework_indicator = enhanced_metrics['rework_indicator']
                    issue.direct_completion = enhanced_metrics['direct_completion']

                    issue.last_updated_at = current_time
                    issues_to_update_metrics.append(issue)

            # Enhanced workflow metrics are updated directly on the issue objects above
            # No separate bulk update needed since SQLAlchemy tracks the changes

        session.commit()
        job_logger.progress(f"[SUCCESS] Successfully processed {total_changelogs_processed} changelogs and updated {len(issues_to_update_metrics)} issue workflow metrics")

        return total_changelogs_processed

    except Exception as e:
        session.rollback()
        job_logger.error(f"Error in changelog processing: {str(e)}")
        return 0


# Legacy calculate_issue_dates function removed - replaced by calculate_enhanced_workflow_metrics


def calculate_enhanced_workflow_metrics(changelogs: List[IssueChangelog], statuses_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate comprehensive workflow metrics from changelog data.

    Args:
        changelogs: List of IssueChangelog database objects (sorted by transition_change_date DESC)
        statuses_dict: Dictionary mapping status external_ids to status objects

    Returns:
        Dictionary containing all enhanced workflow metrics
    """
    if not changelogs:
        return {
            'work_first_committed_at': None,
            'work_first_started_at': None,
            'work_last_started_at': None,
            'work_first_completed_at': None,
            'work_last_completed_at': None,
            'total_work_starts': 0,
            'total_completions': 0,
            'total_backlog_returns': 0,
            'total_work_time_seconds': 0.0,
            'total_review_time_seconds': 0.0,
            'total_cycle_time_seconds': 0.0,
            'total_lead_time_seconds': 0.0,
            'workflow_complexity_score': 0,
            'rework_indicator': False,
            'direct_completion': False
        }

    # Helper function to get flow step category by database ID
    def get_flow_step_category(status_id):
        if not status_id:
            return None
        for status_external_id, status_obj in statuses_dict.items():
            if status_obj.id == status_id:
                # Get the workflow category via status_mapping relationship
                if hasattr(status_obj, 'status_mapping') and status_obj.status_mapping and status_obj.status_mapping.workflow:
                    return getattr(status_obj.status_mapping.workflow, 'step_category', '').lower()
                # Fallback to status category for backward compatibility
                return getattr(status_obj, 'category', '').lower()
        return None

    # Helper function to get status category by database ID (for legacy compatibility)
    def get_status_category(status_id):
        if not status_id:
            return None
        for status_external_id, status_obj in statuses_dict.items():
            if status_obj.id == status_id:
                return getattr(status_obj, 'category', '').lower()
        return None

    # Helper function to check if status is specific 'To Do' status (not category)
    def is_todo_status(status_id):
        if not status_id:
            return False
        for status_external_id, status_obj in statuses_dict.items():
            if status_obj.id == status_id:
                return getattr(status_obj, 'original_name', '').lower() == 'to do'
        return False

    # Initialize metrics
    metrics = {
        'work_first_committed_at': None,
        'work_first_started_at': None,
        'work_last_started_at': None,
        'work_first_completed_at': None,
        'work_last_completed_at': None,
        'total_work_starts': 0,
        'total_completions': 0,
        'total_backlog_returns': 0,
        'total_work_time_seconds': 0.0,
        'total_review_time_seconds': 0.0,
        'total_cycle_time_seconds': 0.0,
        'total_lead_time_seconds': 0.0,
        'workflow_complexity_score': 0,
        'rework_indicator': False,
        'direct_completion': False
    }

    # Process changelogs in original order (newest first) for proper "first" vs "last" logic
    # "first" = oldest occurrence, "last" = newest occurrence

    # Track time spent in each category for aggregation (need chronological order)
    chronological_changelogs = list(reversed(changelogs))
    time_tracking = {}
    last_transition_date = None
    last_status_category = None

    # Calculate time tracking in chronological order
    # TODO: Consider using get_flow_step_category for more granular tracking
    for changelog in changelogs:
        from_category = get_status_category(changelog.from_status_id)
        to_category = get_status_category(changelog.to_status_id)
        transition_date = changelog.transition_change_date

        # Track time spent in previous status
        if last_transition_date and last_status_category:
            time_spent = DateTimeHelper.calculate_time_difference_seconds_float(
                last_transition_date, transition_date
            )
            if time_spent and time_spent > 0:
                if last_status_category not in time_tracking:
                    time_tracking[last_status_category] = 0
                time_tracking[last_status_category] += time_spent

        last_transition_date = transition_date
        last_status_category = to_category

    # Process changelogs in original order (newest first) for milestone tracking
    for changelog in chronological_changelogs:
        from_category = get_status_category(changelog.from_status_id)
        to_category = get_status_category(changelog.to_status_id)
        transition_date = changelog.transition_change_date

        # Count transitions and track timing milestones
        if to_category:
            # Commitment tracking (TO specific 'To Do' statuses)
            if is_todo_status(changelog.to_status_id):
                metrics['total_backlog_returns'] += 1
                # First commitment = oldest (always update, will be last in DESC order)
                metrics['work_first_committed_at'] = transition_date

            # Work starts (TO 'In Progress')
            if to_category == 'in progress':
                metrics['total_work_starts'] += 1
                # Last work start = newest (first in DESC order) - only set once
                if not metrics['work_last_started_at']:
                    metrics['work_last_started_at'] = transition_date
                # First work start = oldest (always update, will be last in DESC order)
                metrics['work_first_started_at'] = transition_date

            # Completions (TO 'Done')
            elif to_category == 'done':
                metrics['total_completions'] += 1
                # Last completion = newest (first in DESC order) - only set once
                if not metrics['work_last_completed_at']:
                    metrics['work_last_completed_at'] = transition_date
                # First completion = oldest (always update, will be last in DESC order)
                metrics['work_first_completed_at'] = transition_date

    # Aggregate time metrics
    metrics['total_work_time_seconds'] = time_tracking.get('in progress', 0.0)
    metrics['total_review_time_seconds'] = time_tracking.get('to do', 0.0)

    # Calculate cycle time (first start to last completion)
    if metrics['work_first_started_at'] and metrics['work_last_completed_at']:
        metrics['total_cycle_time_seconds'] = DateTimeHelper.calculate_time_difference_seconds_float(
            metrics['work_first_started_at'], metrics['work_last_completed_at']
        ) or 0.0

    # Calculate lead time (first commitment to last completion)
    if metrics['work_first_committed_at'] and metrics['work_last_completed_at']:
        metrics['total_lead_time_seconds'] = DateTimeHelper.calculate_time_difference_seconds_float(
            metrics['work_first_committed_at'], metrics['work_last_completed_at']
        ) or 0.0

    # Calculate pattern metrics
    metrics['workflow_complexity_score'] = (
        (metrics['total_backlog_returns'] * 2) +
        max(0, metrics['total_completions'] - 1)
    )

    metrics['rework_indicator'] = metrics['total_work_starts'] > 1

    # Calculate direct completion
    metrics['direct_completion'] = _calculate_direct_completion(
        metrics, changelogs, statuses_dict
    )

    return metrics


def _calculate_direct_completion(metrics: Dict, changelogs: List, statuses_dict: Dict[str, Any]) -> bool:
    """
    Calculate if the most recent completion was direct (without work).

    Returns True if:
    1. Never worked at all (total_work_starts = 0), OR
    2. Worked in past, but last completion was direct from 'To Do' to 'Done'
    """
    if not metrics['work_last_completed_at']:
        return False

    # Case 1: Never worked at all
    if metrics['total_work_starts'] == 0:
        return True

    # Case 2: Check if last completion was direct (To Do → Done)
    if metrics['work_last_started_at'] and metrics['work_last_completed_at']:
        # If last completion is after last work start, check the transition
        if metrics['work_last_completed_at'] > metrics['work_last_started_at']:
            # Find the changelog entry for the last completion
            for changelog in changelogs:
                if changelog.transition_change_date == metrics['work_last_completed_at']:
                    # Check if this was a To Do category → Done category transition
                    from_category = None
                    to_category = None

                    for status_external_id, status_obj in statuses_dict.items():
                        if status_obj.id == changelog.from_status_id:
                            from_category = getattr(status_obj, 'category', '').lower()
                        if status_obj.id == changelog.to_status_id:
                            to_category = getattr(status_obj, 'category', '').lower()

                    return from_category == 'to do' and to_category == 'done'

    return False


# Legacy date calculation functions removed - replaced by calculate_enhanced_workflow_metrics


def extract_issue_dev_details(session: Session, integration, jira_client, issues_with_external_ids: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Extract development details for issues that have code_changed = True.

    Args:
        session: Database session
        integration: Integration object
        jira_client: Jira API client
        issues_with_external_ids: List of dicts with 'key', 'external_id', and 'id' for issues

    Returns:
        Dictionary with extraction results
    """
    try:
        logger.info(f"Starting Jira development details extraction for {len(issues_with_external_ids)} issues")

        processed_dev_status_data = []  # Store processed dev_status data for GitHub
        issues_processed = 0
        prs_found_in_dev_status = 0

        for issue_data in issues_with_external_ids:
            try:
                # Extract data from the issue_data dict
                issue_key = issue_data['key']
                issue_external_id = issue_data['external_id']
                issue_id = issue_data['id']

                if not issue_external_id:
                    logger.warning(f"Issue {issue_key} has no external_id")
                    continue

                # Fetch development details from Jira using the client method
                dev_details = jira_client.get_issue_dev_details(issue_external_id)
                if not dev_details:
                    logger.debug(f"No development details found for issue {issue_key}")
                    continue

                # Store the raw dev_details for GitHub processing
                processed_dev_status_data.append({
                    'issue_id': issue_id,
                    'issue_key': issue_key,
                    'issue_external_id': issue_external_id,
                    'dev_details': dev_details
                })

                # Count pull requests in development details (don't save to database yet)
                detail = dev_details.get('detail', [])
                for detail_item in detail:
                    # Pull requests are at the same level as branches in the detail object
                    pull_requests = detail_item.get('pullRequests', [])
                    prs_found_in_dev_status += len(pull_requests)

                issues_processed += 1



                if issues_processed % 10 == 0:
                    logger.info(f"Processed development details for {issues_processed} of {len(issues_with_external_ids)} issues so far")

            except Exception as e:
                logger.error(f"Error processing development details for issue {issue_key}: {e}")
                continue

        logger.info(f"Successfully processed development details for {issues_processed} issues, found {prs_found_in_dev_status} pull requests in dev_status data")

        return {
            'success': True,
            'issues_processed': issues_processed,
            'pull_requests_found_in_dev_status': prs_found_in_dev_status,
            'processed_dev_status_data': processed_dev_status_data
        }

    except Exception as e:
        logger.error(f"Error in issue development details extraction: {e}")
        return {
            'success': False,
            'error': str(e),
            'issues_processed': 0,
            'pull_requests_found_in_dev_status': 0,
            'processed_dev_status_data': []
        }








