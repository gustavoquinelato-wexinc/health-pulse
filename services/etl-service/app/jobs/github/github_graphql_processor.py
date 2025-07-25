"""
GitHub GraphQL Data Processor
Processes GraphQL response data and converts it to database format.
"""

from typing import Dict, Any, List, Optional
from app.core.logging_config import get_logger
from app.core.utils import DateTimeHelper
from app.models.unified_models import PullRequest, PullRequestReview, PullRequestCommit, PullRequestComment

logger = get_logger(__name__)


class GitHubGraphQLProcessor:
    """Processes GitHub GraphQL response data into database format."""
    
    def __init__(self, integration, repository_id: int):
        """
        Initialize processor.
        
        Args:
            integration: GitHub integration object
            repository_id: Database ID of the repository
        """
        self.integration = integration
        self.repository_id = repository_id

    def process_repository_data(self, repo_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process raw GitHub repository data into database format.

        Args:
            repo_data: Raw repository data from GitHub API

        Returns:
            Processed repository data ready for database insertion
        """
        try:
            # Parse timestamps
            repo_created_at = None
            repo_updated_at = None

            if repo_data.get('created_at'):
                repo_created_at = DateTimeHelper.parse_datetime(repo_data['created_at'])
            if repo_data.get('updated_at'):
                repo_updated_at = DateTimeHelper.parse_datetime(repo_data['updated_at'])

            # Parse pushed_at timestamp
            pushed_at = None
            if repo_data.get('pushed_at'):
                pushed_at = DateTimeHelper.parse_datetime(repo_data['pushed_at'])

            return {
                'external_id': str(repo_data.get('id')),
                'name': repo_data.get('name'),
                'full_name': repo_data.get('full_name'),
                'description': repo_data.get('description'),
                'url': repo_data.get('html_url'),
                'default_branch': repo_data.get('default_branch'),
                'language': repo_data.get('language'),
                'is_private': repo_data.get('private', False),
                'repo_created_at': repo_created_at,
                'repo_updated_at': repo_updated_at,
                'pushed_at': pushed_at,
                'archived': repo_data.get('archived', False),
                'integration_id': getattr(self.integration, 'id', None) if self.integration else None,
                'client_id': getattr(self.integration, 'client_id', None) if self.integration else None,
                'active': True,
                'created_at': DateTimeHelper.now_utc(),
                'last_updated_at': DateTimeHelper.now_utc()
            }

        except Exception as e:
            logger.error(f"Error processing repository data: {e}")
            logger.debug(f"Repository data: {repo_data}")
            return None

    def process_pull_request_node(self, pr_node: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single pull request node from GraphQL response.
        
        Args:
            pr_node: Pull request node from GraphQL response
            
        Returns:
            Processed pull request data for database
        """
        try:
            # Parse timestamps
            pr_created_at = None
            pr_updated_at = None
            merged_at = None
            closed_at = None
            
            if pr_node.get('createdAt'):
                pr_created_at = DateTimeHelper.parse_iso_datetime(pr_node['createdAt'])
            if pr_node.get('updatedAt'):
                pr_updated_at = DateTimeHelper.parse_iso_datetime(pr_node['updatedAt'])
            if pr_node.get('mergedAt'):
                merged_at = DateTimeHelper.parse_iso_datetime(pr_node['mergedAt'])
            if pr_node.get('closedAt'):
                closed_at = DateTimeHelper.parse_iso_datetime(pr_node['closedAt'])

            return {
                'external_id': str(pr_node.get('number')),  # Use PR number as external_id
                'external_repo_id': None,  # Will be set by the caller with repository.external_id
                'repository_id': self.repository_id,
                'issue_id': None,  # Will be linked later if Jira data exists
                'number': pr_node.get('number'),
                'name': pr_node.get('title'),
                'user_name': pr_node.get('author', {}).get('login') if pr_node.get('author') else None,
                'body': pr_node.get('body'),
                'discussion_comment_count': pr_node.get('comments', {}).get('totalCount', 0),
                'review_comment_count': 0,  # Will be calculated from review threads
                'source': None,  # Not available in GraphQL
                'destination': None,  # Not available in GraphQL
                'reviewers': 0,  # Will be calculated from reviews
                'status': pr_node.get('state', '').lower(),
                'url': pr_node.get('url'),
                'pr_created_at': pr_created_at,
                'pr_updated_at': pr_updated_at,
                'closed_at': closed_at,
                'merged_at': merged_at,
                'merged_by': pr_node.get('mergedBy', {}).get('login') if pr_node.get('mergedBy') else None,
                'commit_count': pr_node.get('commits', {}).get('totalCount', 0),
                'additions': pr_node.get('additions', 0),
                'deletions': pr_node.get('deletions', 0),
                'changed_files': pr_node.get('changedFiles', 0),
                'first_review_at': None,  # Will be calculated from reviews
                'rework_commit_count': 0,  # Will be calculated from commits
                'review_cycles': 0,  # Will be calculated from reviews
                'integration_id': getattr(self.integration, 'id', None) if self.integration else None,
                'client_id': getattr(self.integration, 'client_id', None) if self.integration else None,
                'active': True,
                'created_at': DateTimeHelper.now_utc(),
                'last_updated_at': DateTimeHelper.now_utc()
            }
            
        except Exception as e:
            logger.error(f"Error processing pull request node: {e}")
            logger.debug(f"Pull request node data: {pr_node}")
            return None

    def process_commit_nodes(self, commit_nodes: List[Dict[str, Any]], pull_request_id: int) -> List[PullRequestCommit]:
        """
        Process commit nodes from GraphQL response.
        
        Args:
            commit_nodes: List of commit nodes from GraphQL response
            pull_request_id: Database ID of the pull request
            
        Returns:
            List of PullRequestCommit objects
        """
        commits = []
        
        for commit_node in commit_nodes:
            try:
                commit_data = commit_node.get('commit', {})
                
                # Parse timestamps
                authored_date = None
                committed_date = None
                
                if commit_data.get('author', {}).get('date'):
                    authored_date = DateTimeHelper.parse_iso_datetime(commit_data['author']['date'])
                if commit_data.get('committer', {}).get('date'):
                    committed_date = DateTimeHelper.parse_iso_datetime(commit_data['committer']['date'])
                
                commit = PullRequestCommit(
                    external_id=commit_data.get('oid'),  # SHA
                    pull_request_id=pull_request_id,
                    author_name=commit_data.get('author', {}).get('name'),
                    author_email=commit_data.get('author', {}).get('email'),
                    committer_name=commit_data.get('committer', {}).get('name'),
                    committer_email=commit_data.get('committer', {}).get('email'),
                    message=commit_data.get('message'),
                    authored_date=authored_date,
                    committed_date=committed_date,
                    integration_id=getattr(self.integration, 'id', None) if self.integration else None,
                    client_id=getattr(self.integration, 'client_id', None) if self.integration else None,
                    active=True,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                
                commits.append(commit)
                
            except Exception as e:
                logger.error(f"Error processing commit node: {e}")
                continue
        
        return commits

    def process_review_nodes(self, review_nodes: List[Dict[str, Any]], pull_request_id: int) -> List[PullRequestReview]:
        """
        Process review nodes from GraphQL response.
        
        Args:
            review_nodes: List of review nodes from GraphQL response
            pull_request_id: Database ID of the pull request
            
        Returns:
            List of PullRequestReview objects
        """
        reviews = []
        
        for review_node in review_nodes:
            try:
                # Parse timestamp
                submitted_at = None
                if review_node.get('submittedAt'):
                    submitted_at = DateTimeHelper.parse_iso_datetime(review_node['submittedAt'])
                
                review = PullRequestReview(
                    external_id=review_node.get('id'),
                    pull_request_id=pull_request_id,
                    author_login=review_node.get('author', {}).get('login') if review_node.get('author') else None,
                    state=review_node.get('state'),
                    body=review_node.get('body'),
                    submitted_at=submitted_at,
                    integration_id=getattr(self.integration, 'id', None) if self.integration else None,
                    client_id=getattr(self.integration, 'client_id', None) if self.integration else None,
                    active=True,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                
                reviews.append(review)
                
            except Exception as e:
                logger.error(f"Error processing review node: {e}")
                continue
        
        return reviews

    def process_comment_nodes(self, comment_nodes: List[Dict[str, Any]], pull_request_id: int, 
                            comment_type: str = 'issue') -> List[PullRequestComment]:
        """
        Process comment nodes from GraphQL response.
        
        Args:
            comment_nodes: List of comment nodes from GraphQL response
            pull_request_id: Database ID of the pull request
            comment_type: Type of comment ('issue' or 'review')
            
        Returns:
            List of PullRequestComment objects
        """
        comments = []
        
        for comment_node in comment_nodes:
            try:
                # Parse timestamps
                created_at_github = None
                updated_at_github = None
                
                if comment_node.get('createdAt'):
                    created_at_github = DateTimeHelper.parse_iso_datetime(comment_node['createdAt'])
                if comment_node.get('updatedAt'):
                    updated_at_github = DateTimeHelper.parse_iso_datetime(comment_node['updatedAt'])
                
                comment = PullRequestComment(
                    external_id=comment_node.get('id'),
                    pull_request_id=pull_request_id,
                    author_login=comment_node.get('author', {}).get('login') if comment_node.get('author') else None,
                    body=comment_node.get('body'),
                    comment_type=comment_type,
                    path=comment_node.get('path'),  # Only for review comments
                    position=comment_node.get('position'),  # Only for review comments
                    line=comment_node.get('line'),  # Only for review comments
                    created_at_github=created_at_github,
                    updated_at_github=updated_at_github,
                    integration_id=getattr(self.integration, 'id', None) if self.integration else None,
                    client_id=getattr(self.integration, 'client_id', None) if self.integration else None,
                    active=True,
                    created_at=DateTimeHelper.now_utc(),
                    last_updated_at=DateTimeHelper.now_utc()
                )
                
                comments.append(comment)
                
            except Exception as e:
                logger.error(f"Error processing comment node: {e}")
                continue
        
        return comments

    def process_review_thread_nodes(self, review_thread_nodes: List[Dict[str, Any]], 
                                  pull_request_id: int) -> List[PullRequestComment]:
        """
        Process review thread nodes from GraphQL response.
        
        Args:
            review_thread_nodes: List of review thread nodes from GraphQL response
            pull_request_id: Database ID of the pull request
            
        Returns:
            List of PullRequestComment objects (review type)
        """
        all_comments = []
        
        for thread_node in review_thread_nodes:
            try:
                thread_comments = thread_node.get('comments', {}).get('nodes', [])
                comments = self.process_comment_nodes(thread_comments, pull_request_id, 'review')
                all_comments.extend(comments)
                
            except Exception as e:
                logger.error(f"Error processing review thread node: {e}")
                continue
        
        return all_comments

    def calculate_review_metrics(self, reviews: List[Dict[str, Any]], commits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate review-related metrics for a pull request.
        
        Args:
            reviews: List of review data from GraphQL
            commits: List of commit data from GraphQL
            
        Returns:
            Dictionary with calculated metrics
        """
        metrics = {
            'first_review_at': None,
            'reviewers': 0,
            'rework_commit_count': 0,
            'review_cycles': 0
        }
        
        try:
            # Calculate first review time and unique reviewers
            reviewers = set()
            review_times = []
            
            for review in reviews:
                if review.get('submittedAt'):
                    review_time = DateTimeHelper.parse_iso_datetime(review['submittedAt'])
                    review_times.append(review_time)
                    
                if review.get('author', {}).get('login'):
                    reviewers.add(review['author']['login'])
            
            if review_times:
                metrics['first_review_at'] = min(review_times)
            metrics['reviewers'] = len(reviewers)
            
            # Calculate rework commits (commits after first review)
            if metrics['first_review_at'] and commits:
                rework_count = 0
                for commit in commits:
                    commit_data = commit.get('commit', {})
                    if commit_data.get('author', {}).get('date'):
                        commit_date = DateTimeHelper.parse_iso_datetime(commit_data['author']['date'])
                        if commit_date and commit_date > metrics['first_review_at']:
                            rework_count += 1
                metrics['rework_commit_count'] = rework_count
            
            # Calculate review cycles (simplified: number of review rounds)
            metrics['review_cycles'] = len([r for r in reviews if r.get('state') in ['CHANGES_REQUESTED', 'APPROVED']])
            
        except Exception as e:
            logger.error(f"Error calculating review metrics: {e}")
        
        return metrics
