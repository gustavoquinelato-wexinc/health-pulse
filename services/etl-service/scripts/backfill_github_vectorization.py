#!/usr/bin/env python3
"""
Backfill script to queue all existing GitHub entities for vectorization.

This script queues all existing PRs, commits, reviews, comments, and repositories
that were inserted before the vectorization system was implemented.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import get_db_session
from app.models.unified_models import Pr, PrCommit, PrReview, PrComment, Repository, VectorizationQueue
from app.jobs.vectorization_helper import VectorizationQueueHelper
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def backfill_github_vectorization(tenant_id: int = 1):
    """
    Backfill vectorization queue with all existing GitHub entities.
    
    Args:
        tenant_id: Tenant ID to process (default: 1)
    """
    session = next(get_db_session())
    vectorization_helper = VectorizationQueueHelper(tenant_id=tenant_id)
    
    try:
        logger.info(f"Starting GitHub vectorization backfill for tenant {tenant_id}")

        # Get existing queue entries to avoid duplicates
        existing_queue_entries = set()
        existing_entries = session.query(VectorizationQueue.table_name, VectorizationQueue.external_id).filter(
            VectorizationQueue.tenant_id == tenant_id
        ).all()
        for table_name, external_id in existing_entries:
            existing_queue_entries.add((table_name, external_id))

        logger.info(f"Found {len(existing_queue_entries)} existing queue entries to skip")

        # 1. Queue all repositories
        logger.info("Queuing repositories...")
        repositories = session.query(Repository).filter(
            Repository.tenant_id == tenant_id,
            Repository.active == True
        ).all()

        if repositories:
            repo_data = []
            for repo in repositories:
                # Skip if already queued
                if ("repositories", repo.external_id) in existing_queue_entries:
                    continue

                repo_dict = {
                    'external_id': repo.external_id,
                    'name': repo.name,
                    'full_name': repo.full_name,
                    'description': repo.description,
                    'tenant_id': repo.tenant_id
                }
                repo_data.append(repo_dict)

            if repo_data:
                queued_repos = vectorization_helper.queue_entities_for_vectorization(
                    repo_data, "repositories", "insert"
                )
                logger.info(f"Queued {queued_repos} repositories for vectorization")
            else:
                logger.info("All repositories already queued, skipping")
        
        # 2. Queue all PRs
        logger.info("Queuing pull requests...")
        prs = session.query(Pr).filter(
            Pr.tenant_id == tenant_id,
            Pr.active == True
        ).all()

        if prs:
            pr_data = []
            for pr in prs:
                # Skip if already queued
                if ("prs", pr.external_id) in existing_queue_entries:
                    continue

                pr_dict = {
                    'external_id': pr.external_id,
                    'number': pr.number,
                    'name': pr.name,
                    'body': pr.body,
                    'user_name': pr.user_name,
                    'status': pr.status,
                    'tenant_id': pr.tenant_id
                }
                pr_data.append(pr_dict)

            if pr_data:
                queued_prs = vectorization_helper.queue_entities_for_vectorization(
                    pr_data, "prs", "insert"
                )
                logger.info(f"Queued {queued_prs} pull requests for vectorization")
            else:
                logger.info("All PRs already queued, skipping")
        
        # 3. Queue all commits
        logger.info("Queuing commits...")
        commits = session.query(PrCommit).filter(
            PrCommit.tenant_id == tenant_id,
            PrCommit.active == True
        ).all()

        if commits:
            commit_data = []
            for commit in commits:
                # Skip if already queued
                if ("prs_commits", commit.external_id) in existing_queue_entries:
                    continue

                commit_dict = {
                    'external_id': commit.external_id,
                    'author_name': commit.author_name,
                    'author_email': commit.author_email,
                    'message': commit.message,
                    'authored_date': commit.authored_date,
                    'committed_date': commit.committed_date,
                    'tenant_id': commit.tenant_id
                }
                commit_data.append(commit_dict)

            if commit_data:
                queued_commits = vectorization_helper.queue_entities_for_vectorization(
                    commit_data, "prs_commits", "insert"
                )
                logger.info(f"Queued {queued_commits} commits for vectorization")
            else:
                logger.info("All commits already queued, skipping")
        
        # 4. Queue all reviews
        logger.info("Queuing reviews...")
        reviews = session.query(PrReview).filter(
            PrReview.tenant_id == tenant_id,
            PrReview.active == True
        ).all()

        if reviews:
            review_data = []
            for review in reviews:
                # Skip if already queued
                if ("prs_reviews", review.external_id) in existing_queue_entries:
                    continue

                review_dict = {
                    'external_id': review.external_id,
                    'author_login': review.author_login,
                    'state': review.state,
                    'body': review.body,
                    'submitted_at': review.submitted_at,
                    'tenant_id': review.tenant_id
                }
                review_data.append(review_dict)

            if review_data:
                queued_reviews = vectorization_helper.queue_entities_for_vectorization(
                    review_data, "prs_reviews", "insert"
                )
                logger.info(f"Queued {queued_reviews} reviews for vectorization")
            else:
                logger.info("All reviews already queued, skipping")

        # 5. Queue all comments
        logger.info("Queuing comments...")
        comments = session.query(PrComment).filter(
            PrComment.tenant_id == tenant_id,
            PrComment.active == True
        ).all()

        if comments:
            comment_data = []
            for comment in comments:
                # Skip if already queued
                if ("prs_comments", comment.external_id) in existing_queue_entries:
                    continue

                comment_dict = {
                    'external_id': comment.external_id,
                    'author_login': comment.author_login,
                    'body': comment.body,
                    'comment_type': comment.comment_type,
                    'path': comment.path,
                    'line': comment.line,
                    'tenant_id': comment.tenant_id
                }
                comment_data.append(comment_dict)

            if comment_data:
                queued_comments = vectorization_helper.queue_entities_for_vectorization(
                    comment_data, "prs_comments", "insert"
                )
                logger.info(f"Queued {queued_comments} comments for vectorization")
            else:
                logger.info("All comments already queued, skipping")
        
        logger.info("GitHub vectorization backfill completed successfully!")
        
        # Summary
        total_queued = (
            len(repositories) + len(prs) + len(commits) + 
            len(reviews) + len(comments)
        )
        logger.info(f"Total entities queued: {total_queued}")
        logger.info(f"  • Repositories: {len(repositories)}")
        logger.info(f"  • Pull Requests: {len(prs)}")
        logger.info(f"  • Commits: {len(commits)}")
        logger.info(f"  • Reviews: {len(reviews)}")
        logger.info(f"  • Comments: {len(comments)}")
        
    except Exception as e:
        logger.error(f"Error during GitHub vectorization backfill: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    # Run the backfill for tenant 1
    backfill_github_vectorization(tenant_id=1)
